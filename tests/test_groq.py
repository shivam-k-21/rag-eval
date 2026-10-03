import io
import json
from urllib.error import HTTPError, URLError

import pytest

from rag_eval import groq
from rag_eval.cli import main
from rag_eval.types import Doc


def response(text="The Team plan costs $40. [pricing_plans]", finish="stop"):
    return io.BytesIO(json.dumps({"choices": [{"finish_reason": finish,
        "message": {"content": text, "reasoning": "Internal reasoning is not the answer."}}]}).encode())


def generator(monkeypatch, **kwargs):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    return groq.GroqGenerator("openai/gpt-oss-20b", **kwargs)


def test_missing_groq_key_does_not_use_google_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "google-key")
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        groq.GroqGenerator("openai/gpt-oss-20b")


def test_groq_request_contract(monkeypatch):
    calls = []

    def request(req, timeout):
        calls.append((req, timeout))
        return response("Team costs $40. [a] [a]")

    monkeypatch.setattr(groq, "urlopen", request)
    answer = generator(monkeypatch).generate("How much?", [Doc("a", "A", "Team costs $40.")])
    req, timeout = calls[0]
    assert req.full_url == "https://api.groq.com/openai/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer test-groq-key"
    assert "test-groq-key" not in req.full_url and timeout == 120
    payload = json.loads(req.data)
    assert payload["model"] == "openai/gpt-oss-20b"
    assert payload["reasoning_effort"] == "low" and payload["include_reasoning"] is False
    assert payload["max_completion_tokens"] == 2048
    assert payload["messages"][0]["role"] == "system"
    assert "How much?" in payload["messages"][1]["content"]
    assert answer.citations == ["a"] and "Internal reasoning" not in answer.text


@pytest.mark.parametrize("text,expected", [(" INSUFFICIENT_EVIDENCE ", True),
    ("The marker INSUFFICIENT_EVIDENCE is documented. [a]", False)])
def test_exact_abstention(monkeypatch, text, expected):
    monkeypatch.setattr(groq, "urlopen", lambda *a, **kw: response(text))
    assert generator(monkeypatch).generate("q", []).abstained == expected


@pytest.mark.parametrize("text,finish", [("", "stop"), (None, "stop"),
    ("partial", "length"), ("blocked", "content_filter")])
def test_failed_provider_output_is_not_scored(monkeypatch, text, finish):
    monkeypatch.setattr(groq, "urlopen", lambda *a, **kw: response(text, finish))
    with pytest.raises(RuntimeError, match="no answer was scored"):
        generator(monkeypatch).generate("q", [])


@pytest.mark.parametrize("code,header,expected_delay", [(503, None, 5), (429, "12", 12)])
def test_retryable_error_recovers(monkeypatch, code, header, expected_delay):
    calls, sleeps = [], []

    def request(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise HTTPError("https://example.test", code, "temporary", {"Retry-After": header} if header else {}, None)
        return response()

    monkeypatch.setattr(groq, "urlopen", request)
    monkeypatch.setattr(groq.time, "monotonic", lambda: 100)
    monkeypatch.setattr(groq.time, "sleep", sleeps.append)
    assert not generator(monkeypatch).generate("q", []).abstained
    assert len(calls) == 2 and sleeps == [expected_delay]


def test_retry_limit_and_spacing(monkeypatch):
    calls, sleeps = [], []

    def request(*a, **kw):
        calls.append(1)
        raise HTTPError("https://example.test", 503, "temporary", {}, None)

    monkeypatch.setattr(groq, "urlopen", request)
    monkeypatch.setattr(groq.time, "monotonic", lambda: 100)
    monkeypatch.setattr(groq.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError, match="4 attempts"):
        generator(monkeypatch, request_interval=15).generate("q", [])
    assert len(calls) == 4 and sleeps == [15, 15, 20]


@pytest.mark.parametrize("code,headers", [(401, {}), (404, {}), (429, {}), (429, {"Retry-After": "120"})])
def test_permanent_or_long_quota_errors_stop_and_hide_secrets(monkeypatch, code, headers):
    calls = []

    def request(*a, **kw):
        calls.append(1)
        raise HTTPError("https://example.test", code, "test-groq-key", headers, io.BytesIO(b"test-groq-key"))

    monkeypatch.setattr(groq, "urlopen", request)
    with pytest.raises(RuntimeError, match=f"HTTP {code}") as exc:
        generator(monkeypatch).generate("q", [])
    assert len(calls) == 1 and "test-groq-key" not in str(exc.value)


def test_cli_report_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(groq, "urlopen", lambda *a, **kw: response())
    main(["--generator", "groq", "--model", "openai/gpt-oss-20b", "--retriever", "bm25",
          "--limit", "1", "--out", str(tmp_path)])
    raw = (tmp_path / "report_bm25_groq.json").read_text()
    report = json.loads(raw)
    assert report["end_to_end"]["pass_rate"] == 1
    assert report["config"]["generator"] == "groq"
    assert report["config"]["reasoning_effort"] == "low"
    assert "test-groq-key" not in raw


def test_invalid_response_and_connection_errors(monkeypatch):
    monkeypatch.setattr(groq, "urlopen", lambda *a, **kw: io.BytesIO(b"null"))
    with pytest.raises(RuntimeError, match="no usable answer"):
        generator(monkeypatch).generate("q", [])
    monkeypatch.setattr(groq, "urlopen", lambda *a, **kw: io.BytesIO(b"bad-json"))
    with pytest.raises(RuntimeError, match="invalid JSON"):
        generator(monkeypatch).generate("q", [])

    def fail(*a, **kw):
        raise URLError("offline")

    monkeypatch.setattr(groq, "urlopen", fail)
    with pytest.raises(RuntimeError, match="internet connection"):
        generator(monkeypatch).generate("q", [])


def test_cli_requires_groq_model():
    with pytest.raises(SystemExit) as exc:
        main(["--generator", "groq"])
    assert exc.value.code == 2
