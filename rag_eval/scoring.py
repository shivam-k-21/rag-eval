"""Conservative text helpers. These are rules, not a semantic entailment model."""
import re

from .text import content_tokens, split_sentences

SAFE_REFUSAL = re.compile(
    r"i (?:cannot|can't|will not|won't) (?:print|reveal|share|disclose) (?:my|the) system prompt[.!]?",
    re.I,
)


def is_safe_refusal(claim: str) -> bool:
    return bool(SAFE_REFUSAL.fullmatch(claim.strip()))


def substantive_text(text: str, refusal_check=is_safe_refusal) -> str:
    return " ".join(s for s in split_sentences(text) if not refusal_check(s))


def claim_tokens(text: str) -> set[str]:
    # Remove conversational wrappers; retain facts, subjects, units and predicates.
    text = re.sub(r"\bbased on the provided sources\b[:,]?", "", text, flags=re.I)
    text = re.sub(r"\bfrom the date of\b", "", text, flags=re.I)
    text = re.sub(r"\b(?:you have|current|additionally|after creating it|afterward)\b", "", text, flags=re.I)
    aliases = {"tier": "plan", "pricing": "price", "priced": "cost", "covered": "guarantee"}
    text = " ".join(aliases.get(w.lower(), w) for w in re.findall(r"\w+(?:\.\d+)?", text))
    return set(content_tokens(text)) - {"no", "cannot", "can", "hav"}


def negative(text: str) -> bool:
    return bool(re.search(r"\b(?:no|not|never|cannot|can't|won't|without)\b", text, re.I))


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\b\d+(?:\.\d+)?\b", text))


def subjects(text: str) -> set[str]:
    generic = {"The", "A", "An", "I", "You", "It", "No", "Yes", "Based", "Customers", "After",
               "Additionally", "Note", "All", "New", "If", "Files", "Workspaces", "Backups", "Support",
               "Single", "Community", "Archived", "When", "Deleted", "Restores", "Enterprise",
               "Data", "Affected", "Custom", "Maximum", "Current", "This", "That", "There",
               "Our", "Your", "Their", "They", "We"}
    named = {w.lower() for w in re.findall(r"\b[A-Z][A-Za-z]+\b", text) if w not in generic}
    named.update(re.findall(r"\b(?:starter|team|enterprise|ios|android|analytics)\b", text.lower()))
    return named
