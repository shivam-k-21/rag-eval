"""Source attribution / citation-faithfulness checks.

Faithfulness = share of answer sentences whose content words are supported by the *cited*
chunks (not merely by anything retrieved). The default judge is lexical: cheap and
deterministic. Swap in an NLI model or LLM judge through the SupportJudge protocol."""
from __future__ import annotations
import re
from typing import Protocol

from .text import content_tokens, split_sentences
from .types import Answer, Case, Doc

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


def attribute(case: Case, answer: Answer, context_ids: list[str],
              corpus: dict[str, Doc], judge: SupportJudge) -> dict:
    """Citation metrics for one answer. Fields are None when the model abstained."""
    if answer.abstained:
        return dict(faithfulness=None, citations_valid=None, cites_gold=None,
                    citation_precision=None, cites_forbidden=False, citation_ok=None)
    cited = list(dict.fromkeys(answer.citations))
    valid = bool(cited) and all(c in context_ids and c in corpus for c in cited)
    evidence = [corpus[c].text for c in cited if c in corpus]
    sentences = split_sentences(_CITE.sub("", answer.text)) or [""]
    sup = [judge.supported(s, evidence) for s in sentences] if evidence else [False] * len(sentences)
    faith = sum(sup) / len(sup)
    gold = set(case.gold_ids)
    cites_gold = bool(gold & set(cited)) if gold else None
    precision = (len(gold & set(cited)) / len(cited)) if (gold and cited) else (0.0 if gold else None)
    cites_forbidden = bool(set(case.forbidden_ids) & set(cited))
    ok = valid and faith >= 0.999 and not cites_forbidden and (cites_gold is not False)
    return dict(faithfulness=faith, citations_valid=valid, cites_gold=cites_gold,
                citation_precision=precision, cites_forbidden=cites_forbidden, citation_ok=ok)
