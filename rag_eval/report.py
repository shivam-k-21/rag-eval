from __future__ import annotations
import json
import math
from pathlib import Path

DESC = {
    "PASS": "correct, grounded, safe",
    "RETRIEVAL_MISS": "gold chunk not in top-k; generator never saw the evidence",
    "DISTRACTOR_INTERFERENCE": "gold present; fails on retrieved context but succeeds on oracle context, suggesting noise interference",
    "WRONG_ANSWER_GIVEN_GOLD": "generator fails even with oracle context",
    "OVER_ABSTENTION": "refused although evidence was available",
    "UNSUPPORTED_GENERATION": "answered a question the corpus cannot answer",
    "ADVERSARIAL_COMPLIANCE": "followed an injection / asserted stale or false content",
    "CITATION_UNFAITHFUL": "answer right, but citations invalid, unsupporting or from the wrong source",
}


def _p(x):
    return "n/a" if x is None or x != x else f"{x:.3f}"


def _ci(m):
    if m['mean'] != m['mean']:
        return "n/a"
    return f"{m['mean']:.3f} [{m['ci95'][0]:.2f}, {m['ci95'][1]:.2f}]"


def to_markdown(r: dict) -> str:
    c, ret, gen = r["config"], r["retrieval"], r["generation_oracle"]
    ae, ao, e2e = r["attribution_e2e"], r["attribution_oracle"], r["end_to_end"]
    L = [f"# Evaluation report: {c['retriever']} + {c['generator']} (k={c['k']})", "",
         f"Scoring version: {c.get('scoring_version', '1.0')}; judge: {c.get('support_judge', 'LexicalSupportJudge')}; mode: {c.get('evaluation_mode', 'generated_answers')}.", "",
         "## Stage 1: Retrieval (generator not involved)", "",
         f"Scored on {ret['n']} cases with gold evidence. Brackets are 95% bootstrap CIs.", "",
         "| Metric | Value |", "|---|---|"]
    if c.get("evaluation_mode") == "rescore_saved_answers":
        L[2:2] = ["These are regraded saved answers, not a new model run. Retrieval and answer text are unchanged.", ""]
    metrics = [m for m in ret if m.startswith("recall@")] + ["mrr"]
    L += [f"| {m} | {_ci(ret[m])} |" for m in metrics]
    L += ["", "| Slice | n | " + " | ".join(metrics) + " |", "|---|---|" + "---|" * len(metrics)]
    L += [f"| {t} | {v['n']} | " + " | ".join(_p(v[m]) for m in metrics) + " |"
          for t, v in ret["by_type"].items()]
    L += ["", "## Stage 2: Generation with oracle context (retrieval removed)", "",
          f"Overall answer-OK rate: **{_p(gen['answer_ok'])}**. "
          f"Abstention accuracy on no-answer cases: **{_p(gen['abstention_accuracy'])}**.", "",
          "| Case type | n | Answer-OK |", "|---|---|---|"]
    L += [f"| {t} | {v['n']} | {_p(v['answer_ok'])} |" for t, v in gen["by_type"].items()]
    L += ["", "## Stage 3: Source attribution", "",
          "| Metric | End-to-end | Oracle context |", "|---|---|---|",
          f"| Answered cases | {ae['n_answered']} | {ao['n_answered']} |",
          f"| Mean citation faithfulness | {_p(ae['mean_faithfulness'])} | {_p(ao['mean_faithfulness'])} |",
          f"| Citation validity | {_p(ae['citation_validity'])} | {_p(ao['citation_validity'])} |",
          f"| Citation precision vs gold | {_p(ae['citation_precision'])} | {_p(ao['citation_precision'])} |",
          f"| Citation-OK rate | {_p(ae['citation_ok_rate'])} | {_p(ao['citation_ok_rate'])} |",
          f"| Cites a forbidden source | {_p(ae['forbidden_source_cited'])} | {_p(ao['forbidden_source_cited'])} |",
          "", "## End-to-end error analysis", "",
          f"Pass rate **{e2e['pass_rate']:.3f}** (95% CI {e2e['pass_ci95'][0]:.2f}-{e2e['pass_ci95'][1]:.2f}), n={e2e['n']}.", "",
          "| Diagnosis | Count | Meaning |", "|---|---|---|"]
    L += [f"| {k} | {v} | {DESC[k]} |" for k, v in e2e["diagnosis_counts"].items()]
    L += ["", "### Failures", "", "| Case | Type | Diagnosis | Retrieved | Answer |", "|---|---|---|---|---|"]
    for row in r["cases"]:
        if row["diagnosis"] != "PASS":
            cells = [row['id'], row['type'], row['diagnosis'], ', '.join(row['retrieved']), row['e2e_answer'][:90]]
            L.append("| " + " | ".join(str(v).replace("|", "\\|").replace("\n", " ").replace("\r", " ") for v in cells) + " |")
    return "\n".join(L) + "\n"


def write_report(r: dict, out_dir: str | Path, stem: str):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{stem}.json").write_text(json.dumps(_json_safe(r), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out / f"{stem}.md").write_text(to_markdown(r), encoding="utf-8")


def _json_safe(value):
    """Represent undefined numeric metrics as JSON null rather than nonstandard NaN."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value
