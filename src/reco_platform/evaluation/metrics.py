from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import log2

import numpy as np


def ranking_metrics(ranking: list[str], relevant: set[str], k: int) -> dict[str, float]:
    top = list(dict.fromkeys(ranking))[:k]
    hits = [index for index, item in enumerate(top, 1) if item in relevant]
    ideal = min(len(relevant), k)
    return {
        "precision": len(hits) / k,
        "recall": len(hits) / len(relevant) if relevant else 0.0,
        "ndcg": (sum(1 / log2(i + 1) for i in hits) /
                 sum(1 / log2(i + 1) for i in range(1, ideal + 1))) if ideal else 0.0,
        "map": sum(number / i for number, i in enumerate(hits, 1)) / ideal if ideal else 0.0,
    }


def distance(a: set[str], b: set[str]) -> float:
    return 1 - len(a & b) / len(a | b) if a or b else 0.0


def summary(examples, k, items, tags, popularity):
    if not examples:
        return {}
    metrics = [ranking_metrics(ranking, relevant, k) for ranking, relevant in examples]
    exposures = Counter(item for ranking, _ in examples for item in ranking[:k])
    total = sum(popularity.values())
    denomin = total + max(1, len(items))
    novelty = sum(count * -log2((popularity.get(item, 0) + 1) / denomin)
                  for item, count in exposures.items()) / max(1, sum(exposures.values()))
    diversities = []
    for ranking, _ in examples:
        pairs = [distance(tags[a], tags[b]) for a, b in combinations(ranking[:k], 2)]
        diversities.append(float(np.mean(pairs)) if pairs else 0.0)
    head_size = max(1, round(len(items) * 0.2))
    head = set(sorted(items, key=lambda item: (-popularity.get(item, 0), item))[:head_size])
    return {
        **{name: float(np.mean([row[name] for row in metrics])) for name in metrics[0]},
        "coverage": len(exposures) / max(1, len(items)),
        "diversity": float(np.mean(diversities)), "novelty_bits": novelty,
        "head_share": sum(exposures[item] for item in head) / max(1, sum(exposures.values())),
        "cases": len(examples), "k": k,
    }
