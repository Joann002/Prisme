import json

import pandas as pd
import pytest

from reco_platform.config import load_configs
from reco_platform.data import demo_dataset, read_dataset, write_dataset
from reco_platform.domains.base import INTERACTION_COLUMNS, ITEM_COLUMNS, adapter_for, frequency_filter

CONFIG = load_configs()
CASE = {
    "movies": {
        "movies.csv": "movieId,title,genres\n10,Test (1999),Action|Drama\n",
        "ratings.csv": "userId,movieId,rating,timestamp\n8,10,4,1700000000\n8,10,5,1700000010\n",
    },
    "books": {
        "books.csv": "book_id,title,authors,original_publication_year\n10,Test,Auteur,1988\n",
        "ratings.csv": "user_id,book_id,rating\n8,10,5\n",
    },
    "games": {
        "games.csv": "appid,name,genres\n10,Test,Action\n",
        "reviews.csv": "steamid,appid,voted_up,timestamp_created\n8,10,true,1700000010\n",
    },
    "music": {
        "artists.csv": "artist_id,name,tags\n10,Test,Jazz\n",
        "listens.csv": "user_id,artist_id,plays,timestamp\n8,10,12,2023-01-01\n",
    },
    "recipes": {
        "RAW_recipes.csv": 'id,name,tags,description\n10,Test,"[\'baking\']",Un plat.\n',
        "RAW_interactions.csv": "user_id,recipe_id,date,rating\n8,10,2023-01-01,0\n8,10,2023-01-02,5\n",
    },
}


@pytest.mark.parametrize("slug", CASE)
def test_real_source_contracts(slug, tmp_path):
    for name, body in CASE[slug].items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    adapter = adapter_for(CONFIG[slug])
    result = adapter.load(tmp_path, filter_interactions=False)
    assert list(result.interactions.columns) == INTERACTION_COLUMNS
    assert set(ITEM_COLUMNS).issubset(result.items)
    assert result.items["domaine"].tolist() == [slug]
    assert result.items["titre"].tolist() == ["Test"]
    assert result.interactions["item_id"].tolist() == ["10"]
    assert len(result.interactions) == 1
    assert bool(result.interactions["timestamp"].notna().all()) is (slug != "books")
    if slug == "movies":
        assert result.interactions["feedback"].tolist() == [5]
    if slug == "games":
        assert result.interactions["feedback"].tolist() == [1]


def test_steam_playtime_alternative(tmp_path):
    (tmp_path / "games.csv").write_text(CASE["games"]["games.csv"])
    (tmp_path / "reviews.csv").write_text(
        "steamid,appid,playtime_forever,timestamp_created\n8,10,42,1700000010\n")
    result = adapter_for(CONFIG["games"]).load(tmp_path, filter_interactions=False)
    assert result.interactions["feedback"].iloc[0] == pytest.approx(.7)


def test_frequency_prunes_to_fixed_point():
    frame = pd.DataFrame({"user_id": ["u", "u", "v", "v", "v", "w", "w"],
                          "item_id": ["a", "b", "a", "c", "d", "c", "d"]})
    result = frequency_filter(frame, 2, 2)
    assert set(result["user_id"]) == {"v", "w"}
    assert set(result["item_id"]) == {"c", "d"}


def test_parquet_version_integrity(tmp_path):
    config = CONFIG["movies"]
    baseline = demo_dataset(config)
    directory = tmp_path / config.slug
    manifest = write_dataset(baseline, directory, "synthetic")
    restored = read_dataset(config, tmp_path)
    assert manifest["files"]["items.parquet"]["rows"] == len(restored.items)
    pd.testing.assert_frame_equal(baseline.interactions, restored.interactions)
    filename = manifest["files"]["items.parquet"].get("path", "items.parquet")
    (directory / filename).write_bytes(b"damaged")
    with pytest.raises(ValueError, match="Empreinte"):
        read_dataset(config, tmp_path)
    assert json.loads((directory / "manifest.json").read_text())["temporal"]


def test_every_config_has_demo_data():
    assert len(CONFIG) == 5
    for slug, config in CONFIG.items():
        result = demo_dataset(config)
        assert len(result.items) >= 15
        assert result.interactions["timestamp"].notna().all()
        assert (result.interactions["feedback"] >= config.positive).any(), slug
