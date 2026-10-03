"""Gemini generateContent adapter using only the Python standard library."""
from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .generation import ABSTAIN_MARKER, ABSTAIN_TEXT, AnthropicGenerator, _CITE
from .types import Answer, Doc


class GeminiGenerator:
    name = "gemini"
    SYSTEM = AnthropicGenerator.SYSTEM + " Keep the answer concise."

    def __init__(self, model: str | None = None, max_tokens: int = 2048,
                 request_interval: float = 0, max_retries: int = 3):
        if not model or not re.fullmatch(r"(?:models/)?[\w.\-]+", model):
            raise ValueError("Gemini requires an explicit valid model id (--model)")
        if not math.isfinite(request_interval) or request_interval < 0:
            raise ValueError("request_interval must be finite and nonnegative")
        if max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or not 0 <= max_retries <= 5:
            raise ValueError("max_retries must be an integer between 0 and 5")
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            raise ValueError("Set GEMINI_API_KEY in your terminal environment before using Gemini")
        self._api_key = key
        self.model = model.removeprefix("models/")
        self.max_tokens = max_tokens
        self.request_interval = request_interval
        self.max_retries = max_retries
        self._last_request = None

    def generate(self, question: str, context: list[Doc]) -> Answer:
        sources = "\n\n".join(f'<source id="{d.id}">\n{d.text}\n</source>' for d in context)
        payload = {
            "systemInstruction": {"parts": [{"text": self.SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": f"{sources}\n\nQuestion: {question}"}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": self.max_tokens},
        }
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key},
            method="POST",
        )
        result = self._request_json(request)
        try:
            candidate = result.get("candidates", [])[0]
            if candidate.get("finishReason") != "STOP":
                raise RuntimeError("Gemini did not finish normally (blocked or truncated response); no answer was scored.")
            text = "".join(part.get("text", "") for part in candidate.get("content", {}).get("parts", [])
                           if not part.get("thought", False)).strip()
        except (IndexError, AttributeError, TypeError):
            raise RuntimeError("Gemini returned no usable candidate; no answer was scored.") from None
        if not text:
            raise RuntimeError("Gemini returned an empty answer; no answer was scored.")
        if text == ABSTAIN_MARKER:
            return Answer(ABSTAIN_TEXT, [], abstained=True)
        return Answer(text, list(dict.fromkeys(_CITE.findall(text))))

    def _request_json(self, request: Request):
        retry_delay = 0.0
        for attempt in range(self.max_retries + 1):
            delay = retry_delay
            if self._last_request is not None:
                delay = max(delay, self.request_interval - (time.monotonic() - self._last_request))
            if delay > 0:
                time.sleep(delay)
            self._last_request = time.monotonic()
            try:
                with urlopen(request, timeout=120) as response:
                    return json.load(response)
            except HTTPError as exc:
                code = exc.code
                headers = exc.headers
                quota_hint = self._quota_hint(exc) if code == 429 else ""
                exc.close()
                if code in {500, 502, 503, 504} and attempt < self.max_retries:
                    retry_delay = float(min(60, 5 * 2 ** attempt))
                    # Honor numeric Retry-After values within the bounded wait policy.
                    try:
                        requested_delay = float(headers.get("Retry-After", "0")) if headers else 0
                    except (TypeError, ValueError):
                        requested_delay = 0
                    if math.isfinite(requested_delay) and requested_delay > 60:
                        raise RuntimeError(f"Gemini HTTP {code}. The provider requested a longer wait; retry later.") from None
                    if math.isfinite(requested_delay):
                        retry_delay = max(retry_delay, requested_delay)
                    effective_delay = max(retry_delay, self.request_interval - (time.monotonic() - self._last_request))
                    print(f"Gemini HTTP {code}; retry {attempt + 1}/{self.max_retries} "
                          f"in {effective_delay:.0f}s.", file=sys.stderr, flush=True)
                    continue
                hints = {
                    400: "Check the API key, model id, and model generation settings.",
                    401: "Check GEMINI_API_KEY.",
                    403: "Check key permissions and Gemini API availability for your project.",
                    404: "Check that --model names an available generateContent model.",
                    429: "Quota or rate limit reached; check AI Studio quotas and increase --request-interval or wait for reset.",
                }
                hint = (f"Temporary provider failure persisted after {attempt + 1} attempts; "
                        "wait and retry, or choose another available model.") if code in {500, 502, 503, 504} else hints.get(code, "The provider request failed; retry later.")
                if quota_hint:
                    hint = quota_hint
                # Never display provider bodies that might echo credentials or input.
                raise RuntimeError(f"Gemini HTTP {code}. {hint}") from None
            except (URLError, TimeoutError, OSError):
                raise RuntimeError("Could not reach Gemini; check your internet connection and retry.") from None
            except (ValueError, TypeError):
                raise RuntimeError("Gemini returned an invalid JSON response.") from None

    def _quota_hint(self, error: HTTPError) -> str:
        """Interpret structured quota metadata without displaying raw provider text."""
        try:
            body = json.loads(error.read(65536))
            details = body.get("error", {}).get("details", [])
            if not isinstance(details, list):
                return ""
        except (ValueError, TypeError, AttributeError, OSError):
            return ""
        categories, limits, waits = set(), [], []
        for detail in details:
            if not isinstance(detail, dict):
                continue
            kind = detail.get("@type", "")
            if kind == "type.googleapis.com/google.rpc.QuotaFailure":
                violations = detail.get("violations", [])
                if not isinstance(violations, list):
                    continue
                for violation in violations:
                    if not isinstance(violation, dict):
                        continue
                    identifier = " ".join(str(violation.get(k, "")) for k in ("quotaId", "quotaMetric")).lower()
                    if "perday" in identifier or "per_day" in identifier:
                        categories.add("daily")
                    if "perminute" in identifier or "per_minute" in identifier:
                        categories.add("per-minute")
                    limit = str(violation.get("quotaValue", ""))
                    if re.fullmatch(r"\d{1,12}", limit):
                        limits.append(int(limit))
            elif kind == "type.googleapis.com/google.rpc.RetryInfo":
                delay = str(detail.get("retryDelay", ""))
                if re.fullmatch(r"\d{1,8}(?:\.\d{1,6})?s", delay):
                    waits.append(float(delay[:-1]))
        if not categories and not limits and not waits:
            return ""
        messages = []
        if 0 in limits:
            messages.append("Google reports a quota limit of 0; this project currently has no capacity under that quota. Check model eligibility and project quotas in AI Studio.")
        if "daily" in categories:
            messages.append("A daily quota was exceeded. Wait for its midnight Pacific reset or use another free-tier model with available quota; increasing request spacing will not fix a daily limit.")
        if "per-minute" in categories:
            messages.append("A per-minute quota was exceeded. Wait for recovery and increase --request-interval to fit your project's request/token limits.")
        if limits and 0 not in limits:
            messages.append("Reported quota limit(s): " + ", ".join(str(n) for n in sorted(set(limits))) + ".")
        if waits:
            messages.append(f"Google suggests retrying after at least {max(waits):g}s; this does not override a daily or zero quota.")
        return " ".join(messages)
