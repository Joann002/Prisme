from math import log2

import pandas as pd
import pytest

from reco_platform.evaluation.metrics import distance, ranking_metrics, summary
from reco_platform.evaluation.split import leave_last_out


def test_rank_metrics_hand_calculated():
    result = ranking_metrics(["x", "a", "b"], {"a", "b", "c"}, 3)
    assert result["precision"] == pytest.approx(2 / 3)
    assert result["recall"] == pytest.approx(2 / 3)
    assert result["map"] == pytest.approx((1 / 2 + 2 / 3) / 3)
    assert result["ndcg"] == pytest.approx((1 / log2(3) + 0.5) / (1 + 1 / log2(3) + 0.5))


def test_empty_and_short_rankings():
    assert all(value == 0 for value in ranking_metrics([], set(), 3).values())
    assert ranking_metrics(["a", "a"], {"a"}, 3)["precision"] == pytest.approx(1 / 3)
    assert ranking_metrics(["a"], {"a", "b"}, 1)["recall"] == 0.5


def test_coverage_diversity_novelty_and_popularity_share():
    stats = summary([(["a", "b"], {"a"})], 2, {"a", "b", "c"},
                    {"a": {"x"}, "b": {"x", "y"}, "c": set()}, {"a": 2, "b": 1})
    assert stats["coverage"] == pytest.approx(2 / 3)
    assert stats["diversity"] == pytest.approx(0.5)
    assert stats["novelty_bits"] == pytest.approx((1 + log2(3)) / 2)
    assert stats["head_share"] == 0.5
    assert distance(set(), set()) == 0.0


def test_leave_last_out_excludes_same_time_and_later_dislikes():
    events = pd.DataFrame([
        ("u", "a", "2024-01-01", 4), ("u", "b", "2024-01-02", 5),
        ("u", "c", "2024-01-02", 5), ("u", "d", "2024-01-03", 1),
        ("v", "e", "2024-01-01", 5),
    ], columns=["user_id", "item_id", "timestamp", "feedback"])
    events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True)
    train, test = leave_last_out(events, 3.5)
    assert set(train["item_id"]) == {"a", "e"}
    assert set(test["item_id"]) == {"b", "c"}
    with pytest.raises(ValueError, match="dates"):
        leave_last_out(events.assign(timestamp=pd.NaT), 3.5)
