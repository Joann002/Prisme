import pytest


def test_domains_health_and_catalog(client):
    assert client.get("/health").json()["status"] == "ok"
    assert {row["slug"] for row in client.get("/domains").json()} == {"movies", "books", "games", "music", "recipes"}
    page = client.get("/catalog/movies", params={"q": "dune", "limit": 1})
    assert page.status_code == 200
    assert page.json()["items"][0]["item_id"] == "dune"
    assert client.get("/catalog/movies", params={"offset": -1}).status_code == 422
    assert client.get("/catalog/nope").status_code == 404


def test_recommend_known_and_new_user(client):
    for user in ("demo-001", "unseen"):
        response = client.get("/recommend", params={"domain": "games", "user_id": user, "k": 5})
        assert response.status_code == 200
        assert len(response.json()["recommendations"]) == 5


def test_explicit_catalog_and_cross(client):
    start = {"domain": "movies", "liked": ["dune", "interstellar"], "k": 6}
    first = client.post("/recommend/items", json=start)
    assert first.status_code == 200, first.text
    assert first.json() == client.post("/recommend/items", json=start).json()
    assert all(item["explanation"] for item in first.json()["recommendations"])
    result = client.post("/cross-recommend", json={"source_domain": "movies", "target_domain": "books",
                                                   "liked": ["dune"]})
    assert result.status_code == 200
    assert result.json()["recommendations"][0]["titre"] == "Dune"


def test_similar_disambiguates(client):
    assert client.get("/similar/dune").status_code == 409
    assert client.get("/similar/interstellar").status_code == 200
    result = client.get("/similar/dune?domain=books&k=3")
    assert result.status_code == 200
    assert len(result.json()["recommendations"]) == 3
    assert client.get("/similar/unknown").status_code == 404


@pytest.mark.parametrize("payload, status", [
    ({"domain": "movies", "liked": ["unknown"]}, 404),
    ({"domain": "Nope", "liked": ["dune"]}, 422),
    ({"domain": "movies", "liked": ["dune"], "k": "3"}, 422),
    ({"domain": "movies", "liked": ["dune"], "model": "missing"}, 422),
    ({"domain": "movies", "liked": ["dune"] * 21}, 422),
    ({"domain": "movies", "extra": "value"}, 422),
])
def test_rejects_invalid_payload(client, payload, status):
    assert client.post("/recommend/items", json=payload).status_code == status


def test_feedback_rate_and_privacy(client, monkeypatch):
    feedback = {"domain": "movies", "item_id": "dune", "vote": "up"}
    runtime = client.app.state.runtime
    runtime.limits.maximum = 1
    assert client.post("/feedback", json=feedback).status_code == 201
    assert client.post("/feedback", json=feedback).status_code == 429
    assert all(len(key) == 4 for key in runtime.feedback_store.totals)
    assert "prisme_feedback" in client.get("/metrics").text
    assert "Confidentialité" in client.get("/privacy").text


def test_oversize_body(client):
    assert client.post("/feedback", content=b"x" * 17000).status_code == 413
    assert client.post("/feedback", content=iter([b"x" * 9000, b"x" * 8000])).status_code == 413
