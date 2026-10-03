"""Retrievers. Anything with .name and .search(query, k) -> [(doc_id, score)] plugs in
(dense, hybrid, reranked...)."""
from __future__ import annotations
import math
from collections import Counter
from typing import Protocol

from .text import content_tokens
from .types import Doc


class Retriever(Protocol):
    name: str
    def search(self, query: str, k: int) -> list[tuple[str, float]]: ...


def _rank(ids, scores, k):
    if k < 1:
        raise ValueError("k must be positive")
    ranked = sorted(zip(ids, scores), key=lambda x: (-x[1], x[0]))
    return [(i, s) for i, s in ranked if s > 0][:k]


class BM25Retriever:
    name = "bm25"

    def __init__(self, docs: list[Doc], k1: float = 1.5, b: float = 0.75):
        self.ids = [d.id for d in docs]
        self.k1, self.b = k1, b
        self.tf = [Counter(content_tokens(d.text)) for d in docs]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = (sum(self.len) / len(self.len) if self.len else 0) or 1.0
        df = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def search(self, query: str, k: int):
        q = set(content_tokens(query))
        scores = []
        for i, c in enumerate(self.tf):
            s = 0.0
            for t in q:
                f = c.get(t, 0)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            scores.append(s)
        return _rank(self.ids, scores, k)


class TfidfRetriever:
    """TF-IDF cosine similarity: a second lexical baseline to compare BM25 against."""
    name = "tfidf"

    def __init__(self, docs: list[Doc]):
        self.ids = [d.id for d in docs]
        toks = [Counter(content_tokens(d.text)) for d in docs]
        df = Counter()
        for c in toks:
            df.update(c.keys())
        n = len(docs)
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1 for t, d in df.items()}
        self.vecs = [self._vec(c) for c in toks]

    def _vec(self, counts):
        v = {t: (1 + math.log(f)) * self.idf.get(t, 0.0) for t, f in counts.items() if t in self.idf}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def search(self, query: str, k: int):
        q = self._vec(Counter(content_tokens(query)))
        scores = [sum(w * v.get(t, 0.0) for t, w in q.items()) for v in self.vecs]
        return _rank(self.ids, scores, k)


RETRIEVERS = {"bm25": BM25Retriever, "tfidf": TfidfRetriever}
