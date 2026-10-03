import io
import json
from urllib.error import HTTPError, URLError

import pytest

from rag_eval import gemini
from rag_eval.cli import main
from rag_eval.types import Doc


def mock_response(monkeypatch, text="The Team plan costs $40. [pricing_plans]", **candidate_fields):
    requests = []

    def open_request(request, timeout):
        requests.append((request, timeout))
        payload = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]},
                                   **candidate_fields}]}
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(gemini, "urlopen", open_request)
    return requests


def generator(monkeypatch, **kwargs):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    return gemini.GeminiGenerator("models/test-model", **kwargs)


def test_missing_key_and_invalid_model_fail_before_requests(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        gemini.GeminiGenerator("test-model")
    with pytest.raises(ValueError, match="model id"):
        gemini.GeminiGenerator("../invalid?key=bad")


def test_request_contract_and_citation_parsing(monkeypatch):
    requests = mock_response(monkeypatch, "Team costs $40. [a] [a]")
    answer = generator(monkeypatch).generate("How much?", [Doc("a", "A", "Team costs $40.")])
    assert answer.citations == ["a"] and not answer.abstained
    request, timeout = requests[0]
    assert request.full_url.endswith("/models/test-model:generateContent")
    assert "fake-key" not in request.full_url
    assert timeout == 120 and request.get_method() == "POST"
    data = json.loads(request.data)
    assert "untrusted DATA" in data["systemInstruction"]["parts"][0]["text"]
    assert "How much?" in data["contents"][0]["parts"][0]["text"]
    assert "Team costs $40." in data["contents"][0]["parts"][0]["text"]
    assert data["generationConfig"]["maxOutputTokens"] == 2048


@pytest.mark.parametrize("text,expected", [(" INSUFFICIENT_EVIDENCE ", True),
    ("The marker is INSUFFICIENT_EVIDENCE. [a]", False)])
def test_exact_abstention_marker(monkeypatch, text, expected):
    mock_response(monkeypatch, text)
    assert generator(monkeypatch).generate("q", []).abstained == expected


@pytest.mark.parametrize("payload", [{}, {"candidates": []},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": []}}]},
    {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "partial"}]}}]}])
def test_provider_failures_are_not_scored_as_abstention(monkeypatch, payload):
    monkeypatch.setattr(gemini, "urlopen", lambda *a, **kw: io.BytesIO(json.dumps(payload).encode()))
    with pytest.raises(RuntimeError, match="no answer was scored"):
        generator(monkeypatch, max_retries=0).generate("q", [])


@pytest.mark.parametrize("code", [403, 404, 429, 503])
def test_http_errors_are_actionable_and_do_not_expose_response_body(monkeypatch, code):
    def fail(*args, **kwargs):
        raise HTTPError("https://example.test", code, "fake-key-for-test", {}, io.BytesIO(b"secret-provider-response"))

    monkeypatch.setattr(gemini, "urlopen", fail)
    with pytest.raises(RuntimeError, match=f"HTTP {code}") as exc:
        generator(monkeypatch, max_retries=0).generate("q", [])
    assert "fake-key" not in str(exc.value) and "secret-provider" not in str(exc.value)


def test_network_failure_and_bad_json(monkeypatch):
    g = generator(monkeypatch)

    def fail(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr(gemini, "urlopen", fail)
    with pytest.raises(RuntimeError, match="internet connection"):
        g.generate("q", [])
    monkeypatch.setattr(gemini, "urlopen", lambda *a, **kw: io.BytesIO(b"not-json"))
    with pytest.raises(RuntimeError, match="invalid JSON"):
        g.generate("q", [])


def test_request_spacing(monkeypatch):
    mock_response(monkeypatch)
    clock = iter([100, 103, 115])
    sleeps = []
    monkeypatch.setattr(gemini.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(gemini.time, "sleep", sleeps.append)
    g = generator(monkeypatch, request_interval=15)
    g.generate("q", [])
    g.generate("q", [])
    assert sleeps == [12]


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_temporary_server_failure_retries_then_succeeds(monkeypatch, code, capsys):
    clock = [100.0]
    sleeps, calls = [], []

    def sleep(delay):
        sleeps.append(delay)
        clock[0] += delay

    def request(*args, **kwargs):
        calls.append(1)
        if len(calls) <= 2:
            raise HTTPError("https://example.test", code, "temporary", {}, None)
        return io.BytesIO(json.dumps({"candidates": [{"finishReason": "STOP",
            "content": {"parts": [{"text": "Team costs $40. [a]"}]}}]}).encode())

    monkeypatch.setattr(gemini.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(gemini.time, "sleep", sleep)
    monkeypatch.setattr(gemini, "urlopen", request)
    answer = generator(monkeypatch).generate("q", [])
    assert answer.citations == ["a"]
    assert len(calls) == 3 and sleeps == [5, 10]
    assert "retry 2/3" in capsys.readouterr().err


def test_retries_remain_bounded_and_respect_request_interval(monkeypatch):
    clock = [100.0]
    sleeps, calls = [], []

    def sleep(delay):
        sleeps.append(delay)
        clock[0] += delay

    def request(*args, **kwargs):
        calls.append(1)
        raise HTTPError("https://example.test", 503, "temporary", {}, None)

    monkeypatch.setattr(gemini.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(gemini.time, "sleep", sleep)
    monkeypatch.setattr(gemini, "urlopen", request)
    with pytest.raises(RuntimeError, match="persisted after 4 attempts"):
        generator(monkeypatch, request_interval=15).generate("q", [])
    assert len(calls) == 4 and sleeps == [15, 15, 20]


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429])
def test_permanent_and_quota_errors_are_not_retried(monkeypatch, code):
    calls = []

    def request(*args, **kwargs):
        calls.append(1)
        raise HTTPError("https://example.test", code, "error", {}, None)

    monkeypatch.setattr(gemini, "urlopen", request)
    with pytest.raises(RuntimeError, match=f"HTTP {code}"):
        generator(monkeypatch).generate("q", [])
    assert len(calls) == 1


@pytest.mark.parametrize("header,expected", [("25", 25), ("invalid", 5), ("nan", 5)])
def test_retry_after_header(monkeypatch, header, expected):
    sleeps, calls = [], []

    def request(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise HTTPError("https://example.test", 503, "temporary", {"Retry-After": header}, None)
        return io.BytesIO(json.dumps({"candidates": [{"finishReason": "STOP",
            "content": {"parts": [{"text": "INSUFFICIENT_EVIDENCE"}]}}]}).encode())

    monkeypatch.setattr(gemini.time, "monotonic", lambda: 100)
    monkeypatch.setattr(gemini.time, "sleep", sleeps.append)
    monkeypatch.setattr(gemini, "urlopen", request)
    assert generator(monkeypatch).generate("q", []).abstained
    assert sleeps == [expected]


def test_long_retry_after_stops_without_shortening_provider_wait(monkeypatch):
    def request(*args, **kwargs):
        raise HTTPError("https://example.test", 503, "temporary", {"Retry-After": "120"}, None)

    monkeypatch.setattr(gemini, "urlopen", request)
    with pytest.raises(RuntimeError, match="longer wait"):
        generator(monkeypatch).generate("q", [])


@pytest.mark.parametrize("quota_id,limit,expected", [
    ("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "20", "daily quota"),
    ("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "5", "per-minute quota"),
    ("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "0", "quota limit of 0"),
])
def test_structured_quota_diagnostics(monkeypatch, quota_id, limit, expected):
    payload = {"error": {"message": "fake-key-for-test secret raw error", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
            {"quotaId": quota_id, "quotaValue": limit}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "42.5s"},
    ]}}

    def fail(*args, **kwargs):
        raise HTTPError("https://example.test", 429, "quota", {}, io.BytesIO(json.dumps(payload).encode()))

    monkeypatch.setattr(gemini, "urlopen", fail)
    with pytest.raises(RuntimeError) as exc:
        generator(monkeypatch).generate("q", [])
    assert expected in str(exc.value)
    assert "42.5s" in str(exc.value)
    assert "fake-key-for-test" not in str(exc.value) and "raw error" not in str(exc.value)


@pytest.mark.parametrize("payload", [b"not-json", b"null", b'{"error":{"details":null}}'])
def test_malformed_quota_metadata_uses_generic_message(monkeypatch, payload):
    def fail(*args, **kwargs):
        raise HTTPError("https://example.test", 429, "quota", {}, io.BytesIO(payload))

    monkeypatch.setattr(gemini, "urlopen", fail)
    with pytest.raises(RuntimeError, match="Quota or rate limit reached"):
        generator(monkeypatch).generate("q", [])


def test_gemini_cli_smoke_run_and_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")
    requests = mock_response(monkeypatch)
    main(["--generator", "gemini", "--model", "test-model", "--retriever", "bm25",
          "--limit", "1", "--out", str(tmp_path)])
    raw = (tmp_path / "report_bm25_gemini.json").read_text()
    report = json.loads(raw)
    assert len(requests) == 2 and len(report["cases"]) == 1
    assert report["config"]["model"] == "test-model"
    assert report["config"]["case_limit"] == 1
    assert report["config"]["total_input_cases"] == 37
    assert report["config"]["request_interval"] == 0
    assert "fake-key-for-test" not in raw


def test_cli_stops_without_writing_report_on_provider_error(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

    def fail(*args, **kwargs):
        raise HTTPError("https://example.test", 429, "rate limited", {}, None)

    monkeypatch.setattr(gemini, "urlopen", fail)
    with pytest.raises(SystemExit) as exc:
        main(["--generator", "gemini", "--model", "test-model", "--retriever", "bm25",
              "--limit", "1", "--out", str(tmp_path)])
    assert exc.value.code == 1
    assert "Quota or rate limit" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("args", [["--generator", "gemini"], ["--limit", "0"],
    ["--request-interval", "nan"], ["--request-interval", "-1"], ["--request-interval", "1"]])
def test_cli_rejects_invalid_live_options(args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
