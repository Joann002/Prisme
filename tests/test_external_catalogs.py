from io import BytesIO
from urllib.error import HTTPError

import pandas as pd

from reco_platform.config import load_configs
from reco_platform.data import demo_dataset
from reco_platform.domains import external
from reco_platform.service import Recommender


def test_catalog_request_retries_temporary_rate_limit(monkeypatch):
    replies = iter((HTTPError("https://example.org", 429, "rate limited", {"Retry-After": "2"}, None),
                    BytesIO(b'{"docs": []}')))
    pauses = []

    def request(*args, **kwargs):
        reply = next(replies)
        if isinstance(reply, HTTPError):
            raise reply
        return reply

    monkeypatch.setattr(external, "urlopen", request)
    monkeypatch.setattr(external.time, "sleep", pauses.append)
    assert external.fetch_json("https://example.org") == {"docs": []}
    assert pauses == [2]


def test_external_sources_merge_with_the_demo_and_preserve_favorites(monkeypatch):
    replies = {
        "https://fr.wikipedia.org/w/api.php": {"query": {"pages": [
            {"pageid": 10, "title": "Dune (film, 2021)", "fullurl": "https://fr.wikipedia.org/wiki/Dune",
             "lastrevid": 42, "extract": "Un film de science-fiction."},
            {"pageid": 11, "title": "Avatar (film, 2009)", "fullurl": "https://fr.wikipedia.org/wiki/Avatar"},
        ]}},
        "https://fr.wikibooks.org/w/api.php": {"query": {"pages": [
            {"pageid": 12, "title": "Livre de cuisine/Khao soy", "fullurl": "https://fr.wikibooks.org/wiki/Khao"},
        ]}},
        "https://openlibrary.org/search.json": {"docs": [
            {"key": "/works/OL123W", "title": "Catalogue des étoiles", "author_name": ["Alice"],
             "subject": ["Science Fiction"], "cover_i": 4, "first_publish_year": 2023},
        ]},
        "https://www.freetogame.com/api/games": [
            {"id": 15, "title": "Exploration cosmique", "genre": "Strategy",
             "freetogame_profile_url": "https://www.freetogame.com/orbite",
             "thumbnail": "javascript:alert(1)"},
        ],
        "https://musicbrainz.org/ws/2/release-group/": {"release-groups": [
            {"id": "6b0b187c-554a-3793-9054-aca6237d0e9c", "title": "Voyage sonore",
             "artist-credit": [{"name": "Bob"}], "secondary-types": ["Soundtrack"]},
        ]},
    }
    monkeypatch.setattr(external, "fetch_json", lambda url, **params: replies[url])
    configs = load_configs()
    datasets = {slug: demo_dataset(config) for slug, config in configs.items()}
    enriched = external.load_external(datasets)
    for slug in configs:
        assert len(enriched[slug].items) == len(datasets[slug].items) + 1
        pd.testing.assert_frame_equal(enriched[slug].interactions, datasets[slug].interactions)
    engine = Recommender(configs, enriched, only={"tfidf"})
    assert all(group["external_items"] >= 1 for group in engine.metadata())
    dune = engine.catalog("movies", query="Dune")["items"][0]
    assert dune["item_id"] == "dune"
    assert dune["source_url"].endswith("?oldid=42")
    book = engine.catalog("books", query="Catalogue des étoiles")["items"][0]
    assert book["source"] == "Open Library"
    assert "Science-fiction" in book["tags"]
    assert engine.catalog("games", query="Exploration cosmique")["items"][0]["image"] == ""
    assert engine.catalog("recipes", query="Khao soy")["items"][0]["source"] == "Wikilivres"
    feed = engine.recommend_feed({"movies": ["dune", "interstellar", "inception"]}, k=1)
    assert all(len(matches) == 1 and matches[0]["source_url"] for matches in feed.values())


def test_unavailable_provider_preserves_the_landing_catalogue(monkeypatch):
    config = load_configs()["books"]
    dataset = demo_dataset(config)

    def unavailable(*args, **kwargs):
        raise TimeoutError

    monkeypatch.setattr(external, "fetch_json", unavailable)
    assert external.load_external({"books": dataset})["books"] is dataset
