from dataclasses import replace

import numpy as np

from reco_platform.config import load_configs
from reco_platform.data import demo_dataset
from reco_platform.service import Recommender


def test_models_are_deterministic_and_do_not_return_seeds(engine):
    liked = ["dune", "inception", "interstellar"]
    assert {"popular", "tfidf", "knn", "svd", "hybrid"}.issubset(engine.models("movies"))
    for model in engine.models("movies"):
        first = engine.recommend("movies", liked=liked, model=model, k=10)
        second = engine.recommend("movies", liked=liked, model=model, k=10)
        assert first == second
        assert len(first) == 10
        assert not set(liked).intersection(item["item_id"] for item in first)
        assert all(item["explanation"] and np.isfinite(item["score"]) for item in first)


def test_new_user_and_cold_item(engine):
    cold = engine.recommend("books", user="unknown", model="hybrid", k=5)
    popular = engine.recommend("books", model="popular", k=5)
    assert cold == popular
    config = load_configs()["movies"]
    data = demo_dataset(config)
    kept = data.interactions.loc[data.interactions["item_id"].ne("arrival")]
    test = Recommender({"movies": config}, {"movies": replace(data, interactions=kept)}, only={"tfidf"})
    assert test.domain("movies").model.counts[test.domain("movies").model.item_index["arrival"]] == 0
    result = test.recommend("movies", liked=["interstellar"], model="tfidf", k=5, candidates={"arrival"})
    assert result[0]["item_id"] == "arrival"
    assert "Interstellar" in result[0]["explanation"]


def test_cross_domain_returns_adaptation_and_ignores_unaligned_users(engine):
    result = engine.cross_recommend("movies", "books", ["dune"], k=5)
    assert result[0]["item_id"] == "dune"
    configs = {slug: load_configs()[slug] for slug in ("movies", "books")}
    datasets = {slug: replace(demo_dataset(config), demo=False) for slug, config in configs.items()}
    external = Recommender(configs, datasets, only=set())
    a = external.cross_recommend("movies", "books", ["dune"], method="hybrid")
    b = external.cross_recommend("movies", "books", ["dune"], method="tfidf")
    assert a == b


def test_known_user_excludes_dislikes_as_well(engine):
    slug, user = "games", "demo-015"
    seen = engine.domain(slug).model.seen[user]
    result = engine.recommend(slug, user=user, k=10)
    assert seen.isdisjoint(item["item_id"] for item in result)
