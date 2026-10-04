"""Independently testable evaluation stages.

  Stage 1  evaluate_retrieval   retriever only          -> Recall@K, MRR
  Stage 2  run_generation       generator on a *given* context. Feed it oracle context
                                (gold + hard negatives) to isolate generation from retrieval.
  Stage 3  score_answers        answer correctness + citation faithfulness
  Stage 4  diagnose             combines stages into one root-cause label per case
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass

from .attribution import ConservativeSupportJudge, SupportJudge, attribute
from .scoring import substantive_text
from .metrics import bootstrap_ci, mean, recall_at_k, reciprocal_rank
from .types import Answer, Case, Doc, validate_dataset

# --- root-cause taxonomy ----------------------------------------------------------------
PASS = "PASS"
RETRIEVAL_MISS = "RETRIEVAL_MISS"                    # gold chunk never reached the generator
DISTRACTOR_INTERFERENCE = "DISTRACTOR_INTERFERENCE"  # gold present, answer fails despite succeeding on oracle context
WRONG_ANSWER_GIVEN_GOLD = "WRONG_ANSWER_GIVEN_GOLD"  # generation fails even with oracle context
OVER_ABSTENTION = "OVER_ABSTENTION"                  # refused although evidence was present
UNSUPPORTED_GENERATION = "UNSUPPORTED_GENERATION"    # answered an unanswerable question
ADVERSARIAL_COMPLIANCE = "ADVERSARIAL_COMPLIANCE"    # followed injection / asserted stale or false content
CITATION_UNFAITHFUL = "CITATION_UNFAITHFUL"          # right answer, but citations invalid / unsupporting / wrong source

TAXONOMY = [PASS, RETRIEVAL_MISS, DISTRACTOR_INTERFERENCE, WRONG_ANSWER_GIVEN_GOLD,
            OVER_ABSTENTION, UNSUPPORTED_GENERATION, ADVERSARIAL_COMPLIANCE, CITATION_UNFAITHFUL]


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


# --- Stage 1 ---------------------------------------------------------------------------
def evaluate_retrieval(retriever, cases: list[Case], ks=(1, 3, 5), depth: int | None = None) -> dict:
    if not ks or any(k < 1 for k in ks):
        raise ValueError("Retrieval cutoffs must be positive and nonempty")
    depth = max(ks) if depth is None else depth
    if depth < max(ks):
        raise ValueError("Retrieval depth must cover every cutoff")
    per = {}
    for c in cases:
        ranked = [d for d, _ in retriever.search(c.question, depth)]
        row = {"ranked": ranked}
        if c.gold_ids:
            row.update({f"recall@{k}": recall_at_k(ranked, c.gold_ids, k) for k in ks})
            row["rr"] = reciprocal_rank(ranked, c.gold_ids)
        per[c.id] = row
    scored = [r for c in cases if c.gold_ids for r in [per[c.id]]]
    summary = {"n": len(scored)}
    for k in ks:
        vals = [r[f"recall@{k}"] for r in scored]
        summary[f"recall@{k}"] = {"mean": mean(vals), "ci95": bootstrap_ci(vals)}
    rr = [r["rr"] for r in scored]
    summary["mrr"] = {"mean": mean(rr), "ci95": bootstrap_ci(rr)}
    by_type = defaultdict(list)
    for c in cases:
        if c.gold_ids:
            by_type[c.type].append(per[c.id])
    summary["by_type"] = {t: {"n": len(rs), "mrr": mean(r["rr"] for r in rs),
                              **{f"recall@{k}": mean(r[f"recall@{k}"] for r in rs) for k in ks}}
                          for t, rs in by_type.items()}
    return {"per_case": per, "summary": summary}


# --- Stage 2 ---------------------------------------------------------------------------
def run_generation(generator, cases: list[Case], contexts: dict[str, list[Doc]],
                   checkpoint=None, progress=None, stage="e2e") -> dict[str, Answer]:
    answers = {}
    for index, case in enumerate(cases, 1):
        if progress:
            progress(stage, case.id, index, len(cases), "starting")
        if checkpoint:
            answer, cached = checkpoint.generate(generator, case, contexts[case.id], stage)
        else:
            answer, cached = generator.generate(case.question, contexts[case.id]), False
        answers[case.id] = answer
        if progress:
            progress(stage, case.id, index, len(cases), "cached" if cached else "saved" if checkpoint else "complete")
    return answers


def oracle_context(case: Case, corpus: dict[str, Doc], fallback_ids: list[str]) -> list[Doc]:
    """Gold chunks plus the case's hard negatives (negatives first: the conservative order).
    Unanswerable cases have no gold, so the best available evidence is what retrieval returns."""
    if not case.gold_ids:
        return [corpus[i] for i in fallback_ids]
    ids = list(dict.fromkeys([*case.forbidden_ids, *case.gold_ids]))
    return [corpus[i] for i in ids]


# --- Stage 3 ---------------------------------------------------------------------------
@dataclass
class AnswerScore:
    abstained: bool
    correct: bool | None        # None when the case has no reference answer
    forbidden_phrase: bool
    answer_ok: bool
    faithfulness: float | None
    citations_valid: bool | None
    cites_gold: bool | None
    citation_precision: float | None
    cites_forbidden: bool
    citation_ok: bool | None


def score_answer(case: Case, answer: Answer, context_ids: list[str], corpus: dict[str, Doc],
                 judge: SupportJudge) -> AnswerScore:
    text = _norm(answer.text)
    correct = None if not case.answers else any(_norm(a) in text for a in case.answers)
    from .scoring import is_safe_refusal
    forbidden_text = _norm(substantive_text(answer.text, getattr(judge, "safe_refusal", is_safe_refusal)))
    forbidden = any(_norm(p) in forbidden_text for p in case.forbidden_phrases)
    if case.must_abstain:
        ok = answer.abstained and not forbidden
    elif case.answers:
        ok = (not answer.abstained) and bool(correct) and not forbidden
    else:  # e.g. false-premise: any answer is fine as long as it does not assert forbidden content
        ok = not forbidden
    return AnswerScore(abstained=answer.abstained, correct=correct, forbidden_phrase=forbidden,
                       answer_ok=ok, **attribute(case, answer, context_ids, corpus, judge))


def score_answers(cases, answers, contexts, corpus, judge=None) -> dict[str, AnswerScore]:
    judge = judge or ConservativeSupportJudge()
    return {c.id: score_answer(c, answers[c.id], [d.id for d in contexts[c.id]], corpus, judge) for c in cases}


# --- Stage 4 ---------------------------------------------------------------------------
def diagnose(case: Case, ranked: list[str], k: int, e2e: AnswerScore, oracle: AnswerScore) -> str:
    gold_in_ctx = any(g in ranked[:k] for g in case.gold_ids) if case.gold_ids else None
    if e2e.answer_ok and e2e.citation_ok is not False:
        return PASS
    if e2e.forbidden_phrase:
        return ADVERSARIAL_COMPLIANCE
    if case.must_abstain:
        return UNSUPPORTED_GENERATION
    if e2e.answer_ok:  # answer fine, attribution not
        return CITATION_UNFAITHFUL
    if case.gold_ids and not gold_in_ctx:
        return RETRIEVAL_MISS
    if e2e.abstained:
        return OVER_ABSTENTION
    return DISTRACTOR_INTERFERENCE if oracle.answer_ok else WRONG_ANSWER_GIVEN_GOLD


# --- orchestration ----------------------------------------------------------------------
def run_eval(cases, docs, retriever, generator, k: int = 3, ks=(1, 3, 5), judge=None,
             checkpoint=None, progress=None) -> dict:
    validate_dataset(cases, docs)
    if k < 1:
        raise ValueError("k must be positive")
    if not ks or any(cutoff < 1 for cutoff in ks):
        raise ValueError("Retrieval cutoffs must be positive and nonempty")
    judge = judge or ConservativeSupportJudge()
    corpus = {d.id: d for d in docs}
    retr = evaluate_retrieval(retriever, cases, ks, depth=max(max(ks), k))
    e2e_ctx = {c.id: [corpus[i] for i in retr["per_case"][c.id]["ranked"][:k]] for c in cases}
    orc_ctx = {c.id: oracle_context(c, corpus, retr["per_case"][c.id]["ranked"][:k]) for c in cases}
    e2e_ans = run_generation(generator, cases, e2e_ctx, checkpoint, progress, "e2e")
    orc_ans = run_generation(generator, cases, orc_ctx, checkpoint, progress, "oracle")
    e2e = score_answers(cases, e2e_ans, e2e_ctx, corpus, judge)
    orc = score_answers(cases, orc_ans, orc_ctx, corpus, judge)

    rows = []
    for c in cases:
        ranked = retr["per_case"][c.id]["ranked"]
        rows.append({
            "id": c.id, "type": c.type, "tags": list(c.tags), "question": c.question,
            "gold_ids": list(c.gold_ids), "must_abstain": c.must_abstain, "retrieved": ranked[:k],
            "retrieval_hit": (any(g in ranked[:k] for g in c.gold_ids) if c.gold_ids else None),
            "e2e_answer": e2e_ans[c.id].text, "e2e": asdict(e2e[c.id]),
            "e2e_citations": e2e_ans[c.id].citations,
            "oracle_context": [d.id for d in orc_ctx[c.id]],
            "oracle_citations": orc_ans[c.id].citations,
            "oracle_answer": orc_ans[c.id].text, "oracle": asdict(orc[c.id]),
            "diagnosis": diagnose(c, ranked, k, e2e[c.id], orc[c.id]),
        })
    config = {"retriever": retriever.name, "generator": generator.name, "k": k,
              "ks": list(ks), "support_judge": type(judge).__name__}
    config["scoring_version"] = getattr(judge, "scoring_version", "2.0")
    for field in ("min_coverage", "model", "max_tokens", "request_interval", "max_retries", "reasoning_effort"):
        if hasattr(generator, field):
            config[field] = getattr(generator, field)
    if hasattr(judge, "threshold"):
        config["support_threshold"] = judge.threshold
    if hasattr(judge, "model"):
        config["judge_model"] = judge.model
    return {"config": config,
            "retrieval": retr["summary"], "generation_oracle": _gen_summary(rows, "oracle"),
            "attribution_e2e": _attr_summary(rows, "e2e"), "attribution_oracle": _attr_summary(rows, "oracle"),
            "end_to_end": _e2e_summary(rows), "cases": rows}


def _gen_summary(rows, key):
    out = {"answer_ok": mean(r[key]["answer_ok"] for r in rows), "by_type": {}}
    for t in sorted({r["type"] for r in rows}):
        rs = [r for r in rows if r["type"] == t]
        out["by_type"][t] = {"n": len(rs), "answer_ok": mean(r[key]["answer_ok"] for r in rs)}
    unans = [r for r in rows if r["must_abstain"]]
    out["abstention_accuracy"] = mean(r[key]["abstained"] for r in unans) if unans else float("nan")
    return out


def _attr_summary(rows, key):
    ans = [r[key] for r in rows if not r[key]["abstained"]]
    f = lambda name: [a[name] for a in ans if a[name] is not None]
    return {"n_answered": len(ans), "mean_faithfulness": mean(f("faithfulness")),
            "citation_validity": mean(f("citations_valid")), "citation_precision": mean(f("citation_precision")),
            "citation_ok_rate": mean(f("citation_ok")),
            "forbidden_source_cited": mean(a["cites_forbidden"] for a in ans) if ans else float("nan")}


def _e2e_summary(rows):
    counts = Counter(r["diagnosis"] for r in rows)
    by_type = {t: dict(Counter(r["diagnosis"] for r in rows if r["type"] == t))
               for t in sorted({r["type"] for r in rows})}
    return {"n": len(rows), "pass_rate": counts[PASS] / len(rows),
            "pass_ci95": bootstrap_ci([float(r["diagnosis"] == PASS) for r in rows]),
            "diagnosis_counts": {c: counts.get(c, 0) for c in TAXONOMY},
            "by_type": by_type}
