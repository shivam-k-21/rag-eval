"""Retrieval metrics + bootstrap confidence intervals."""
from __future__ import annotations
import random
from typing import Sequence


def recall_at_k(ranked: Sequence[str], gold: Sequence[str], k: int) -> float:
    gold = set(gold)
    return len(gold & set(ranked[:k])) / len(gold) if gold else float("nan")


def reciprocal_rank(ranked: Sequence[str], gold: Sequence[str]) -> float:
    gold = set(gold)
    for i, d in enumerate(ranked, 1):
        if d in gold:
            return 1.0 / i
    return 0.0


def mean(xs: Sequence[float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def bootstrap_ci(xs: Sequence[float], n: int = 2000, alpha: float = 0.05, seed: int = 0):
    """Percentile bootstrap CI for the mean. Small eval sets => wide intervals; report them."""
    xs = list(xs)
    if not xs:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    means = sorted(mean([rng.choice(xs) for _ in xs]) for _ in range(n))
    return (means[int(alpha / 2 * n)], means[int((1 - alpha / 2) * n) - 1])
