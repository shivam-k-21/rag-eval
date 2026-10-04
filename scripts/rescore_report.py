"""Regrade saved answers without calling a provider or changing original reports."""
import argparse
import copy
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rag_eval.attribution import ConservativeSupportJudge, LexicalSupportJudge
from rag_eval.judges import GroqSupportJudge
from rag_eval.semantic import StructuredSupportJudge
from rag_eval.evaluate import score_answer, diagnose, _gen_summary, _attr_summary, _e2e_summary
from rag_eval.report import write_report
from rag_eval.types import Answer, load_cases, load_docs, validate_dataset

ROOT = Path(__file__).resolve().parent.parent


def rescore(original, cases, docs, judge):
    validate_dataset(cases, docs)
    result = copy.deepcopy(original)
    corpus = {d.id: d for d in docs}
    by_id = {c.id: c for c in cases}
    for row in result["cases"]:
        case = by_id[row["id"]]
        if case.question != row["question"]:
            raise ValueError(f"Question changed for {case.id}; replay is not comparable")
        if list(case.gold_ids) != row["gold_ids"] or case.type != row["type"] or case.must_abstain != row["must_abstain"]:
            raise ValueError(f"Evidence labels or case type changed for {case.id}; retrieval aggregates cannot be reused")
        for stage, ids_key in (("e2e", "retrieved"), ("oracle", "oracle_context")):
            answer = Answer(row[f"{stage}_answer"], row[f"{stage}_citations"], row[stage]["abstained"])
            row[stage] = asdict(score_answer(case, answer, row[ids_key], corpus, judge))
        from rag_eval.evaluate import AnswerScore
        row["diagnosis"] = diagnose(case, row["retrieved"], original["config"]["k"],
                                    AnswerScore(**row["e2e"]), AnswerScore(**row["oracle"]))
    result["generation_oracle"] = _gen_summary(result["cases"], "oracle")
    result["attribution_e2e"] = _attr_summary(result["cases"], "e2e")
    result["attribution_oracle"] = _attr_summary(result["cases"], "oracle")
    result["end_to_end"] = _e2e_summary(result["cases"])
    result["config"].update(scoring_version=getattr(judge, "scoring_version", "2.0"), support_judge=type(judge).__name__,
                             evaluation_mode="rescore_saved_answers")
    if hasattr(judge, "threshold"):
        result["config"]["support_threshold"] = judge.threshold
    else:
        result["config"].pop("support_threshold", None)
    if hasattr(judge, "model"):
        result["config"]["judge_model"] = judge.model
    else:
        result["config"].pop("judge_model", None)
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report")
    ap.add_argument("--corpus", default=ROOT / "data/corpus.jsonl")
    ap.add_argument("--cases", default=ROOT / "data/cases.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--judge", choices=["structured", "conservative", "lexical", "groq"], default="conservative")
    ap.add_argument("--judge-model")
    args = ap.parse_args(argv)
    original = json.loads(Path(args.report).read_text())
    fingerprint = hashlib.sha256(Path(args.corpus).read_bytes()).hexdigest()
    expected = original.get("config", {}).get("inputs", {}).get("corpus", {}).get("sha256")
    if expected != fingerprint:
        ap.error("Corpus fingerprint missing or changed; do not regrade against different evidence")
    output = Path(args.out)
    if output.resolve() == Path(args.report).parent.resolve():
        ap.error("Use a separate output directory to preserve the original report")
    if args.judge == "groq":
        if not args.judge_model:
            ap.error("--judge groq requires --judge-model and makes additional API requests")
        try:
            judge = GroqSupportJudge(args.judge_model, checkpoint_dir=output / ".judge-checkpoints", progress=True)
        except ValueError as exc:
            ap.error(str(exc))
    else:
        judge = {"structured": StructuredSupportJudge, "conservative": ConservativeSupportJudge,
                 "lexical": LexicalSupportJudge}[args.judge]()
    result = rescore(original, load_cases(args.cases), load_docs(args.corpus), judge)
    result["config"]["original_report"] = str(Path(args.report).resolve())
    result["config"]["original_report_sha256"] = hashlib.sha256(Path(args.report).read_bytes()).hexdigest()
    result["config"]["reviewed_cases_sha256"] = hashlib.sha256(Path(args.cases).read_bytes()).hexdigest()
    write_report(result, output, Path(args.report).stem + "_rescored")
    print(json.dumps(result["end_to_end"], indent=2))


if __name__ == "__main__":
    main()
