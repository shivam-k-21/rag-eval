"""Shared text utilities: tokenisation, light stemming, sentence splitting."""
import re

STOPWORDS = frozenset(
    "a an the of to in on for per by with and or is are was were be been it its this that "
    "these those there their what which who whom when where why how does do did can could "
    "i my me we our you your at as from about not than then so if much many".split()
)

_TOKEN = re.compile(r"\w+(?:\.\d+)?")
_SENT = re.compile(r"(?<=[.!?])\s+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def stem(word: str) -> str:
    """Deliberately crude suffix stripper (applied identically to queries and docs)."""
    for suf in ("ing", "ed", "es", "s", "e"):
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            return word[: -len(suf)]
    return word


def content_tokens(text: str) -> list[str]:
    return [stem(t) for t in tokenize(text) if t not in STOPWORDS]


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENT.split(text.strip()) if s]
