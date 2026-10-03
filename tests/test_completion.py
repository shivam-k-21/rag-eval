import json
from types import SimpleNamespace

import pytest

from rag_eval.cli import main
from rag_eval.evaluate import run_eval
from rag_eval.generation import AnthropicGenerator, ExtractiveGenerator
from rag_eval.report import write_report
from rag_eval.retrieval import BM25Retriever, TfidfRetriever
from rag_eval.types import Answer, Case, Doc, load_cases, validate_dataset
from rag_eval.attribution import LexicalSupportJudge, attribute


@pytest.mark.parametrize("args", [["--k", "0"], ["--min-coverage", "nan"],
                                 ["--retriever", "missing"], ["--generator", "anthropic"]])
def test_cli_rejects_invalid_arguments(args, capsys):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_loader_includes_line_number_and_rejects_duplicates(tmp_path):
    path = tmp_path / "cases.jsonl"
    row = json.dumps({"id": "x", "type": "known", "question": "q"})
    path.write_text(row + "\n" + row)
    with pytest.raises(ValueError, match=r":2: Duplicate id"):
        load_cases(path)
    path.write_text('{"id": "x", "type": "known", "question": "q", "answers": "wrong"}')
    with pytest.raises(ValueError, match="Case.answers"):
        load_cases(path)


def test_dataset_validation_rejects_missing_and_overlapping_sources():
    docs = [Doc("a", "A", "An answer.")]
    with pytest.raises(ValueError, match="unknown document"):
        validate_dataset([Case("x", "known", "q", gold_ids=("missing",))], docs)
    with pytest.raises(ValueError, match="overlap"):
        validate_dataset([Case("x", "known", "q", gold_ids=("a",), forbidden_ids=("a",))], docs)
    with pytest.raises(ValueError, match="nonempty"):
        run_eval([], docs, BM25Retriever(docs), ExtractiveGenerator())


def test_empty_and_stopword_corpora_do_not_crash():
    for cls in (BM25Retriever, TfidfRetriever):
        assert cls([]).search("q", 1) == []
        assert cls([Doc("a", "A", "the and of")]).search("q", 1) == []


def test_custom_cutoffs_and_undefined_metrics_write_strict_json(tmp_path):
    docs = [Doc("a", "A", "Team costs $40.")]
    cases = [Case("u", "unanswerable", "zzzz")]
    report = run_eval(cases, docs, BM25Retriever(docs), ExtractiveGenerator(), ks=(2, 4))
    write_report(report, tmp_path, "report")
    raw = (tmp_path / "report.json").read_text()
    parsed = json.loads(raw, parse_constant=lambda value: pytest.fail(value))
    assert parsed["retrieval"]["mrr"]["mean"] is None
    assert parsed["config"]["min_coverage"] == 0.6
    assert parsed["cases"][0]["oracle_context"] == []
    assert "recall@4" in (tmp_path / "report.md").read_text()


def test_duplicate_citations_do_not_reduce_precision():
    doc = Doc("a", "A", "Team costs $40.")
    result = attribute(Case("k", "known", "q", gold_ids=("a",)),
                       Answer("Team costs $40. [a]", ["a", "a"]), ["a"], {"a": doc}, LexicalSupportJudge())
    assert result["citation_precision"] == 1


def test_anthropic_requires_explicit_model_without_importing_sdk():
    with pytest.raises(ValueError, match="explicit model"):
        AnthropicGenerator()


@pytest.mark.parametrize("text,abstained", [("INSUFFICIENT_EVIDENCE", True),
    ("The marker INSUFFICIENT_EVIDENCE is documented here. [a] [a]", False)])
def test_anthropic_response_parsing_with_mock_client(text, abstained):
    generator = AnthropicGenerator.__new__(AnthropicGenerator)
    generator.model, generator.max_tokens = "test-model", 300
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])

    generator.client = SimpleNamespace(messages=SimpleNamespace(create=create))
    answer = generator.generate("Question?", [Doc("a", "A", "Evidence.")])
    assert answer.abstained == abstained
    assert answer.citations == ([] if abstained else ["a"])
    assert calls[0]["model"] == "test-model"
    assert "Evidence." in calls[0]["messages"][0]["content"]


def test_cli_writes_reproducible_input_metadata(tmp_path):
    main(["--retriever", "bm25", "--out", str(tmp_path)])
    report = json.loads((tmp_path / "report_bm25_extractive.json").read_text())
    assert len(report["config"]["inputs"]["cases"]["sha256"]) == 64
    assert len(report["cases"]) == 37
