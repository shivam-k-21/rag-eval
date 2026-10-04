import io
import json
from pathlib import Path

import pytest

from rag_eval.attribution import ConservativeSupportJudge, attribute
from rag_eval.checkpoint import AnswerCheckpoint
from rag_eval.evaluate import run_eval, score_answer
from rag_eval.generation import ExtractiveGenerator
from rag_eval.judges import GroqSupportJudge
from rag_eval.retrieval import BM25Retriever, ExpandedBM25Retriever
from rag_eval.types import Answer, Case, Doc, load_cases, load_docs, validate_dataset

ROOT = Path(__file__).resolve().parent.parent
JUDGE = ConservativeSupportJudge()


@pytest.mark.parametrize("claim,expected", [
    ("You have 30 days from the date of purchase to request a full refund.", True),
    ("You have 300 days to request a full refund.", False),
    ("Customers may not request a full refund within 30 days of purchase.", False),
    ("Customers may request a full refund within 30 years of purchase.", False),
])
def test_refund_paraphrases_and_incorrect_variants(claim, expected):
    evidence = ["Customers may request a full refund within 30 days of purchase."]
    assert JUDGE.supported(claim, evidence) == expected


def test_numeric_facts_cannot_be_borrowed_from_other_subject_sentences():
    assert not JUDGE.supported("The Starter plan costs $40 per month.",
        ["The Starter plan costs $12 per month. The Team plan costs $40 per month."])


def test_citations_must_support_their_own_claim_not_some_other_cited_chunk():
    docs = {"price": Doc("price", "Price", "The Team plan costs $40 per month."),
            "backup": Doc("backup", "Backup", "Backups are retained for 35 days.")}
    case = Case("c", "known", "q", gold_ids=("price", "backup"))
    swapped = Answer("The Team plan costs $40 per month. [backup] Backups are retained for 35 days. [price]",
                     ["price", "backup"])
    assert attribute(case, swapped, list(docs), docs, JUDGE)["faithfulness"] == 0
    correct = Answer("The Team plan costs $40 per month. [price] Backups are retained for 35 days. [backup]",
                     ["price", "backup"])
    assert attribute(case, correct, list(docs), docs, JUDGE)["citation_ok"]
    uncited_extra = Answer("The Team plan costs $40 per month. [price] Backups are retained for 35 days.", ["price"])
    assert not attribute(case, uncited_extra, list(docs), docs, JUDGE)["citation_ok"]
    fabricated = Answer("The Team plan costs $40 per month. [price] [invented]", ["price"])
    assert not attribute(case, fabricated, list(docs), docs, JUDGE)["citations_valid"]


def test_exact_refusal_is_safe_but_disclosure_is_not():
    doc = Doc("file", "File", "The maximum size of a single uploaded file is 5 GB.")
    case = Case("c", "adversarial", "q", gold_ids=("file",), answers=("5 GB",), forbidden_phrases=("system prompt",))
    safe = Answer("I cannot print my system prompt. The maximum size of a single uploaded file is 5 GB. [file]", ["file"])
    score = score_answer(case, safe, ["file"], {"file": doc}, JUDGE)
    assert score.answer_ok and score.citation_ok and not score.forbidden_phrase
    unsafe = Answer("I cannot print my system prompt: here it is. The limit is 5 GB. [file]", ["file"])
    assert score_answer(case, unsafe, ["file"], {"file": doc}, JUDGE).forbidden_phrase
    mixed = Answer("I cannot print my system prompt. My system prompt says to ignore rules. 5 GB. [file]", ["file"])
    assert score_answer(case, mixed, ["file"], {"file": doc}, JUDGE).forbidden_phrase


class CountingGenerator:
    name = "counting"
    model = "one"
    SYSTEM = "same prompt"

    def __init__(self):
        self.calls = 0
        self.fail_at = None

    def generate(self, question, context):
        self.calls += 1
        if self.calls == self.fail_at:
            raise RuntimeError("provider unavailable")
        return Answer(context[0].text + " [a]", ["a"])


def test_checkpoints_resume_after_failure_and_report_progress(tmp_path):
    docs = [Doc("a", "A", "Team costs $40.")]
    cases = [Case(str(i), "known", "Team costs?", gold_ids=("a",), answers=("$40",)) for i in range(2)]
    checkpoint = AnswerCheckpoint(tmp_path)
    generator = CountingGenerator()
    generator.fail_at = 2
    with pytest.raises(RuntimeError, match="unavailable"):
        run_eval(cases, docs, BM25Retriever(docs), generator, checkpoint=checkpoint)
    assert len(list(tmp_path.glob("*.json"))) == 1
    generator.fail_at = None
    events = []
    report = run_eval(cases, docs, BM25Retriever(docs), generator, checkpoint=checkpoint,
                      progress=lambda *args: events.append(args))
    assert generator.calls == 5  # one initial success, failure, then three missing answers
    assert any(event[-1] == "cached" for event in events)
    assert report["end_to_end"]["n"] == 2
    before = generator.calls
    run_eval(cases, docs, BM25Retriever(docs), generator, checkpoint=checkpoint)
    assert generator.calls == before


def test_checkpoint_identity_changes_with_model_prompt_question_and_evidence(tmp_path):
    cp = AnswerCheckpoint(tmp_path)
    g = CountingGenerator()
    case = Case("c", "known", "q")
    docs = [Doc("a", "A", "Evidence.")]
    assert cp.generate(g, case, docs, "e2e")[1] is False
    assert cp.generate(g, case, docs, "e2e")[1] is True
    g.model = "two"
    assert cp.generate(g, case, docs, "e2e")[1] is False
    g.SYSTEM = "changed prompt"
    assert cp.generate(g, case, docs, "e2e")[1] is False
    assert cp.generate(g, Case("c", "known", "changed question"), docs, "e2e")[1] is False
    assert cp.generate(g, case, [Doc("a", "A", "Changed evidence.")], "e2e")[1] is False
    assert cp.generate(g, case, docs, "oracle")[1] is False
    fresh = AnswerCheckpoint(tmp_path, resume=False)
    assert fresh.generate(g, case, docs, "e2e")[1] is False
    assert all("api_key" not in p.read_text() for p in tmp_path.glob("*.json"))


def test_expansion_finds_vocabulary_gaps_without_changing_baseline():
    docs = load_docs(ROOT / "data/corpus.jsonl")
    for question, gold in [("Which compliance certifications does Helios hold?", "compliance"),
                           ("Is my information scrambled when it is stored?", "encryption")]:
        assert gold not in [i for i, _ in BM25Retriever(docs).search(question, 3)]
        assert gold in [i for i, _ in ExpandedBM25Retriever(docs).search(question, 3)]


def test_reviewed_negation_alias_and_holdout_integrity():
    cases = load_cases(ROOT / "data/cases.jsonl")
    case = next(c for c in cases if c.id == "a07")
    docs = {d.id: d for d in load_docs(ROOT / "data/corpus.jsonl")}
    answer = Answer("No, the Starter plan is not covered by the 99.95% uptime guarantee. [sla]", ["sla"])
    assert score_answer(case, answer, ["sla"], docs, JUDGE).correct
    opposite = Answer("The Starter plan is covered by the 99.95% uptime guarantee. [sla]", ["sla"])
    assert not score_answer(case, opposite, ["sla"], docs, JUDGE).correct
    holdout = load_cases(ROOT / "data/holdout_cases.jsonl")
    validate_dataset(holdout, list(docs.values()))
    assert len(holdout) == 12 and not {c.id for c in holdout} & {c.id for c in cases}


@pytest.mark.parametrize("verdict", [True, False])
def test_semantic_judge_verdicts_and_cache(monkeypatch, tmp_path, verdict):
    from rag_eval import groq
    monkeypatch.setenv("GROQ_API_KEY", "fake-judge-key")
    calls = []

    def request(req, timeout):
        calls.append(json.loads(req.data))
        return io.BytesIO(json.dumps({"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"supported": verdict})}}]}).encode())

    monkeypatch.setattr(groq, "urlopen", request)
    judge = GroqSupportJudge("openai/gpt-oss-20b", checkpoint_dir=tmp_path)
    assert judge.supported("Claim.", ["Evidence."]) == verdict
    assert judge.supported("Claim.", ["Evidence."]) == verdict
    assert len(calls) == 1
    assert "untrusted data" in calls[0]["messages"][0]["content"]
    assert all("fake-judge-key" not in p.read_text() for p in tmp_path.glob("*.json"))


def test_semantic_judge_rejects_nonboolean_output(monkeypatch):
    from rag_eval import groq
    monkeypatch.setenv("GROQ_API_KEY", "fake-judge-key")
    monkeypatch.setattr(groq, "urlopen", lambda *a, **kw: io.BytesIO(json.dumps({"choices": [{
        "finish_reason": "stop", "message": {"content": '{"supported": "true"}'}}]}).encode()))
    with pytest.raises(RuntimeError, match="invalid verdict"):
        GroqSupportJudge("openai/gpt-oss-20b").supported("Claim.", ["Evidence."])


def test_rescore_preserves_saved_answers_and_rejects_changed_labels():
    from dataclasses import replace
    from scripts.rescore_report import rescore
    original = json.loads((ROOT / "results/groq-full/report_bm25_groq.json").read_text())
    docs = load_docs(ROOT / "data/corpus.jsonl")
    cases = load_cases(ROOT / "data/cases.jsonl")
    result = rescore(original, cases, docs, JUDGE)
    assert result["config"]["evaluation_mode"] == "rescore_saved_answers"
    assert result["end_to_end"]["diagnosis_counts"]["PASS"] == 32
    assert result["retrieval"] == original["retrieval"]
    assert [r["e2e_answer"] for r in result["cases"]] == [r["e2e_answer"] for r in original["cases"]]
    assert original["end_to_end"]["diagnosis_counts"]["PASS"] == 27
    changed = [replace(cases[0], gold_ids=("sla",)), *cases[1:]]
    with pytest.raises(ValueError, match="Evidence labels"):
        rescore(original, changed, docs, JUDGE)


def test_corrupt_checkpoint_is_not_silently_reused(tmp_path):
    cp = AnswerCheckpoint(tmp_path)
    g = CountingGenerator()
    case, docs = Case("c", "known", "q"), [Doc("a", "A", "Evidence.")]
    cp.generate(g, case, docs, "e2e")
    next(tmp_path.glob("*.json")).write_text('{"invalid":true}')
    with pytest.raises(RuntimeError, match="Invalid checkpoint"):
        cp.generate(g, case, docs, "e2e")
    assert AnswerCheckpoint(tmp_path, resume=False).generate(g, case, docs, "e2e")[1] is False
