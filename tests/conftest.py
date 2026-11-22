import pytest
from fastapi.testclient import TestClient

from api.main import app
from reco_platform.config import load_configs
from reco_platform.data import demo_dataset
from reco_platform.service import Recommender


@pytest.fixture(scope="session")
def engine():
    configs = load_configs()
    return Recommender(configs, {slug: demo_dataset(row) for slug, row in configs.items()})


@pytest.fixture
def client(monkeypatch, engine):
    monkeypatch.setattr(Recommender, "load", lambda: engine)
    with TestClient(app) as test_client:
        yield test_client
