"""Source attribution / citation-faithfulness checks.

Faithfulness = share of answer sentences whose content words are supported by the *cited*
chunks (not merely by anything retrieved). The default judge is lexical: cheap and
deterministic. Swap in an NLI model or LLM judge through the SupportJudge protocol."""
from __future__ import annotations
import re
from typing import Protocol

from .text import content_tokens, split_sentences
from .types import Answer, Case, Doc
from .scoring import claim_tokens, is_safe_refusal, negative, numbers, subjects

_CITE = re.compile(r"\[[\w\-.:]+\]")


class SupportJudge(Protocol):
    def supported(self, claim: str, evidence: list[str]) -> bool: ...


class LexicalSupportJudge:
    def __init__(self, threshold: float = 0.8):
        if not 0 <= threshold <= 1:
            raise ValueError("Support threshold must be between 0 and 1")
        self.threshold = threshold

    def supported(self, claim: str, evidence: list[str]) -> bool:
        toks = set(content_tokens(claim))
        if not toks:
            return True
        ev = {t for e in evidence for t in content_tokens(e)}
        return len(toks & ev) / len(toks) >= self.threshold


class ConservativeSupportJudge(LexicalSupportJudge):
    """Sentence-level lexical support with numeric, unit and polarity guards.

    Handles a small set of conversational wrappers. Still not semantic entailment.
    """
    def supported(self, claim: str, evidence: list[str]) -> bool:
        toks = claim_tokens(claim)
        if not toks:
            return False
        units = {"day", "hour", "month", "year", "gb", "tb", "minute"}
        numeric = numbers(claim)
        for doc in evidence:
            for sentence in split_sentences(doc):
                ev = claim_tokens(sentence)
                if not subjects(claim) <= subjects(sentence):
                    continue
                if negative(claim) != negative(sentence):
                    continue
                if not (toks & units) <= ev:
                    continue
                if not numeric <= numbers(sentence):
                    continue
                if len(toks & ev) / len(toks) >= self.threshold:
                    return True
        return False


def attribute(case: Case, answer: Answer, context_ids: list[str],
              corpus: dict[str, Doc], judge: SupportJudge) -> dict:
    """Citation metrics for one answer. Fields are None when the model abstained."""
    if answer.abstained:
        return dict(faithfulness=None, citations_valid=None, cites_gold=None,
                    citation_precision=None, cites_forbidden=False, citation_ok=None)
    cited = list(dict.fromkeys(answer.citations))
    inline_ids = re.findall(r"\[([\w\-.:]+)\]", answer.text)
    valid = (bool(cited) and all(c in context_ids and c in corpus for c in cited)
             and all(c in cited for c in inline_ids))
    # Move trailing citation markers inside sentence boundaries, so "Fact. [id]"
    # stays one unit. Score bullets and paragraphs independently.
    text = re.sub(r"([.!?])\s*((?:\[[\w\-.:]+\]\s*)+)", r" \2\1 ", answer.text)
    units = [s for line in text.splitlines() if line.strip() for s in split_sentences(line)]
    sup = []
    for unit in units:
        claim = _CITE.sub("", unit).strip(" *\t")
        if getattr(judge, "safe_refusal", is_safe_refusal)(claim):
            continue
        local_ids = re.findall(r"\[([\w\-.:]+)\]", unit)
        # Inline citations must agree with the adapter's parsed citation list.
        evidence = [corpus[c].text for c in local_ids if c in cited and c in context_ids and c in corpus]
        sup.append(bool(evidence) and judge.supported(claim, evidence))
    if not sup:
        sup = [False]
    faith = sum(sup) / len(sup)
    gold = set(case.gold_ids)
    cites_gold = bool(gold & set(cited)) if gold else None
    precision = (len(gold & set(cited)) / len(cited)) if (gold and cited) else (0.0 if gold else None)
    cites_forbidden = bool(set(case.forbidden_ids) & set(cited))
    ok = valid and faith >= 0.999 and not cites_forbidden and (cites_gold is not False)
    return dict(faithfulness=faith, citations_valid=valid, cites_gold=cites_gold,
                citation_precision=precision, cites_forbidden=cites_forbidden, citation_ok=ok)
