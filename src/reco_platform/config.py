from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).with_name("configs")
MODEL_LABELS = {
    "random": "Aléatoire",
    "popular": "Popularité",
    "tfidf": "Contenu TF-IDF",
    "knn": "Voisins item-item",
    "svd": "Factorisation SVD",
    "als": "Factorisation ALS",
    "semantic": "Contenu sémantique",
    "hybrid": "Hybride",
    "advanced": "Hybride sémantique",
}
MODEL_ORDER = tuple(MODEL_LABELS)


@dataclass(frozen=True)
class DomainConfig:
    slug: str
    label: str
    singular: str
    icon: str
    adapter: str
    source: dict
    min_user: int = 2
    min_item: int = 2
    positive: float = 3.5
    seed: int = 42
    default_model: str = "hybrid"
    models: tuple[str, ...] = ("popular", "tfidf", "svd", "hybrid")
    parameters: dict = field(default_factory=dict)
    tuning: dict = field(default_factory=dict)

    def __post_init__(self):
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", self.slug):
            raise ValueError(f"Identifiant de domaine invalide : {self.slug}")
        if self.default_model not in self.models or set(self.models) - MODEL_LABELS.keys():
            raise ValueError(f"Modèles mal configurés : {self.slug}")
        if min(self.min_user, self.min_item) < 1:
            raise ValueError(f"Seuils de fréquence invalides : {self.slug}")


def load_configs(directory: Path | None = None) -> dict[str, DomainConfig]:
    directory = directory or Path(os.getenv("RECO_CONFIG_DIR", CONFIG_DIR))
    configs = {}
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw["models"] = tuple(raw["models"])
        config = DomainConfig(**raw)
        if config.slug in configs:
            raise ValueError(f"Domaine déclaré deux fois : {config.slug}")
        configs[config.slug] = config
    if not configs:
        raise ValueError(f"Aucun domaine dans {directory}")
    return configs
