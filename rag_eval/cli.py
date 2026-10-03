from __future__ import annotations
import argparse
import hashlib
import math
from importlib.resources import files
from pathlib import Path

from .evaluate import run_eval
from .generation import GENERATORS
from .gemini import GeminiGenerator
from .groq import GroqGenerator
from .report import write_report
from .retrieval import RETRIEVERS
from .types import load_cases, load_docs, validate_dataset

ROOT = Path(__file__).resolve().parent.parent
CLI_GENERATORS = {**GENERATORS, "gemini": GeminiGenerator, "groq": GroqGenerator}


def _default_data():
    local = ROOT / "data"
    return local if (local / "corpus.jsonl").is_file() else files("rag_eval.datasets")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rag_eval", description="Staged RAG reliability evaluation")
    ap.add_argument("--corpus", default=_default_data() / "corpus.jsonl")
    ap.add_argument("--cases", default=_default_data() / "cases.jsonl")
    ap.add_argument("--retriever", default="bm25,tfidf", help="comma list: " + ",".join(RETRIEVERS))
    ap.add_argument("--generator", default="extractive", choices=list(CLI_GENERATORS))
    ap.add_argument("--k", type=int, default=3, help="chunks passed to the generator")
    ap.add_argument("--min-coverage", type=float, default=0.6, help="extractive generator abstention threshold")
    ap.add_argument("--model", default=None, help="model id for --generator anthropic, gemini, or groq")
    ap.add_argument("--limit", type=int, default=None, help="evaluate only the first N cases (smoke check)")
    ap.add_argument("--request-interval", type=float, default=0, help="minimum seconds between Gemini/Groq request starts")
    ap.add_argument("--max-retries", type=int, default=3, help="Gemini/Groq transient-error retries per request (0-5, default 3)")
    ap.add_argument("--out", default=Path.cwd() / "results")
    a = ap.parse_args(argv)

    names = list(dict.fromkeys(n.strip() for n in a.retriever.split(",")))
    if any(n not in RETRIEVERS for n in names):
        ap.error("--retriever must contain names from: " + ", ".join(RETRIEVERS))
    if a.k < 1:
        ap.error("--k must be positive")
    if not 0 <= a.min_coverage <= 1:
        ap.error("--min-coverage must be between 0 and 1")
    if a.generator in {"anthropic", "gemini", "groq"} and not a.model:
        ap.error(f"--generator {a.generator} requires --model with an available model id")
    if a.limit is not None and a.limit < 1:
        ap.error("--limit must be positive")
    if not math.isfinite(a.request_interval) or a.request_interval < 0:
        ap.error("--request-interval must be finite and nonnegative")
    if a.request_interval and a.generator not in {"gemini", "groq"}:
        ap.error("--request-interval is supported by --generator gemini or groq")
    if not 0 <= a.max_retries <= 5:
        ap.error("--max-retries must be between 0 and 5")
    if a.max_retries != 3 and a.generator not in {"gemini", "groq"}:
        ap.error("--max-retries is supported by --generator gemini or groq")

    try:
        docs, cases = load_docs(a.corpus), load_cases(a.cases)
        validate_dataset(cases, docs)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    total_cases = len(cases)
    if a.limit is not None:
        cases = cases[:a.limit]
    gen_kwargs = {"model": a.model} if a.generator in {"anthropic", "gemini", "groq"} else {}
    if a.generator in {"gemini", "groq"}:
        gen_kwargs["request_interval"] = a.request_interval
        gen_kwargs["max_retries"] = a.max_retries
    if a.generator == "extractive":
        gen_kwargs["min_coverage"] = a.min_coverage
    try:
        generator = CLI_GENERATORS[a.generator](**gen_kwargs)
    except ImportError:
        ap.error("Anthropic support requires: pip install 'rag-eval[anthropic]'")
    except ValueError as exc:
        ap.error(str(exc))

    if a.generator in {"anthropic", "gemini", "groq"}:
        print(f"Evaluating {len(cases)}/{total_cases} cases with {a.generator}: "
              f"{2 * len(cases) * len(names)} generation requests planned.", flush=True)

    summary = []
    for name in names:
        try:
            r = run_eval(cases, docs, RETRIEVERS[name](docs), generator, k=a.k)
        except RuntimeError as exc:
            ap.exit(1, f"Evaluation stopped: {exc}\nNo report was written for {name}; partial answers are not saved.\n")
        r["config"]["case_limit"] = a.limit
        r["config"]["total_input_cases"] = total_cases
        r["config"]["inputs"] = {
            label: {"path": str(Path(path).resolve()), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
            for label, path in (("corpus", a.corpus), ("cases", a.cases))
        }
        write_report(r, a.out, f"report_{name}_{a.generator}")
        summary.append(r)

    print(f"\n{len(cases)} cases, {len(docs)} docs, generator={a.generator}, k={a.k}\n")
    hdr = f"{'retriever':<8} {'R@1':>6} {'R@3':>6} {'R@5':>6} {'MRR':>6} | {'oracle OK':>9} {'faith':>6} {'e2e pass':>8}"
    print(hdr + "\n" + "-" * len(hdr))
    for r in summary:
        rt = r["retrieval"]
        print(f"{r['config']['retriever']:<8} {rt['recall@1']['mean']:>6.3f} {rt['recall@3']['mean']:>6.3f} "
              f"{rt['recall@5']['mean']:>6.3f} {rt['mrr']['mean']:>6.3f} | {r['generation_oracle']['answer_ok']:>9.3f} "
              f"{r['attribution_e2e']['mean_faithfulness']:>6.3f} {r['end_to_end']['pass_rate']:>8.3f}")
    print("\nError analysis (end-to-end):")
    for r in summary:
        counts = {k: v for k, v in r["end_to_end"]["diagnosis_counts"].items() if v}
        print(f"  {r['config']['retriever']:<6} {counts}")
    print(f"\nReports written to {a.out}")


if __name__ == "__main__":
    main()
