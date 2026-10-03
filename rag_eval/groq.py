"""Groq chat-completion adapter; no SDK dependency required."""
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


class GroqGenerator:
    name = "groq"
    SYSTEM = AnthropicGenerator.SYSTEM + " Keep the answer concise."

    def __init__(self, model: str | None = None, max_tokens: int = 2048,
                 request_interval: float = 0, max_retries: int = 3):
        if not model or not re.fullmatch(r"[\w.\-]+(?:/[\w.\-]+)*", model):
            raise ValueError("Groq requires an explicit valid model id (--model)")
        if not math.isfinite(request_interval) or request_interval < 0:
            raise ValueError("request_interval must be finite and nonnegative")
        if not isinstance(max_tokens, int) or max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or not 0 <= max_retries <= 5:
            raise ValueError("max_retries must be an integer between 0 and 5")
        key = os.environ.get("GROQ_API_KEY", "").strip()
        if not key:
            raise ValueError("Set GROQ_API_KEY in your terminal environment before using Groq")
        self._api_key = key
        self.model, self.max_tokens = model, max_tokens
        self.request_interval, self.max_retries = request_interval, max_retries
        self.reasoning_effort = "low" if model in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"} else None
        self._last_request = None

    def generate(self, question: str, context: list[Doc]) -> Answer:
        sources = "\n\n".join(f'<source id="{d.id}">\n{d.text}\n</source>' for d in context)
        payload = {"model": self.model, "temperature": 0, "stream": False,
                   "max_completion_tokens": self.max_tokens,
                   "messages": [{"role": "system", "content": self.SYSTEM},
                                {"role": "user", "content": f"{sources}\n\nQuestion: {question}"}]}
        if self.reasoning_effort:
            payload.update(reasoning_effort=self.reasoning_effort, include_reasoning=False)
        request = Request("https://api.groq.com/openai/v1/chat/completions",
                          data=json.dumps(payload).encode("utf-8"), method="POST",
                          headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}",
                                   "User-Agent": "rag-eval/0.1.0"})
        result = self._request_json(request)
        try:
            choice = result["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise RuntimeError("Groq did not finish normally (blocked or truncated response); no answer was scored.")
            text = choice["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise RuntimeError("Groq returned an empty answer; no answer was scored.")
            text = text.strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            raise RuntimeError("Groq returned no usable answer; no answer was scored.") from None
        if text == ABSTAIN_MARKER:
            return Answer(ABSTAIN_TEXT, [], abstained=True)
        return Answer(text, list(dict.fromkeys(_CITE.findall(text))))

    def _request_json(self, request: Request):
        backoff = 0.0
        for attempt in range(self.max_retries + 1):
            delay = backoff
            if self._last_request is not None:
                delay = max(delay, self.request_interval - (time.monotonic() - self._last_request))
            if delay > 0:
                time.sleep(delay)
            self._last_request = time.monotonic()
            try:
                with urlopen(request, timeout=120) as response:
                    return json.load(response)
            except HTTPError as exc:
                code, headers = exc.code, exc.headers
                exc.close()
                try:
                    retry_after = float(headers.get("Retry-After", "nan")) if headers else float("nan")
                except (TypeError, ValueError):
                    retry_after = float("nan")
                bounded_wait = math.isfinite(retry_after) and 0 <= retry_after <= 60
                retryable = code in {500, 502, 503, 504} or (code == 429 and bounded_wait)
                if retryable and attempt < self.max_retries:
                    if math.isfinite(retry_after) and retry_after > 60:
                        raise RuntimeError(f"Groq HTTP {code}. The provider requested a longer wait; retry later.") from None
                    backoff = float(min(60, 5 * 2 ** attempt))
                    if bounded_wait:
                        backoff = max(backoff, retry_after)
                    delay = max(backoff, self.request_interval - (time.monotonic() - self._last_request))
                    print(f"Groq HTTP {code}; retry {attempt + 1}/{self.max_retries} in {delay:.0f}s.",
                          file=sys.stderr, flush=True)
                    continue
                hints = {400: "Check the model id and generation settings.",
                         401: "Check GROQ_API_KEY; a Google AI Studio key cannot authenticate with Groq.",
                         403: "Check Groq organization/model permissions.",
                         404: "Check that --model names an available Groq chat model.",
                         429: "Quota or rate limit reached. Check Groq Console Limits; increase spacing for per-minute limits or wait for daily quota recovery."}
                hint = hints.get(code, f"Provider failure after {attempt + 1} attempts; retry later.")
                if code == 429 and math.isfinite(retry_after) and retry_after >= 0:
                    hint += f" Provider Retry-After: {retry_after:g}s."
                raise RuntimeError(f"Groq HTTP {code}. {hint}") from None
            except (URLError, TimeoutError, OSError):
                raise RuntimeError("Could not reach Groq; check your internet connection and retry.") from None
            except (ValueError, TypeError):
                raise RuntimeError("Groq returned an invalid JSON response.") from None
