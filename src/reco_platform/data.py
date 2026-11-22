from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from reco_platform.config import DomainConfig
from reco_platform.domains.base import Dataset, clean

FIXTURES = Path(__file__).with_name("fixtures")
DEMO_VERSION = "1.0.0"
FORMAT_VERSION = 1


@lru_cache(maxsize=1)
def demo_catalog() -> dict:
    return json.loads((FIXTURES / "catalog.json").read_text(encoding="utf-8"))


def demo_dataset(config: DomainConfig) -> Dataset:
    items = pd.DataFrame(demo_catalog()[config.slug]).assign(domaine=config.slug)
    themes = sorted(items["theme"].unique())
    rng = np.random.default_rng(config.seed + sum(map(ord, config.slug)))
    personas = np.random.default_rng(config.seed)
    popularity = rng.lognormal(0, 0.7, len(items))
    interactions = []
    start = pd.Timestamp("2023-01-01", tz="UTC")
    profiles = personas.integers(len(themes), size=(150, 2))
    for number, (theme, second) in enumerate(profiles):
        weights = np.where(items["theme"].eq(themes[theme]), 8.5,
                           np.where(items["theme"].eq(themes[second]), 3.0, 0.6)) * popularity
        size = rng.integers(5, min(11, len(items) - 2))
        weights[-2:] *= 0.2
        if number < len(profiles) // 3:
            weights[-2:] = 0
        choices = rng.choice(len(items), size, p=weights / weights.sum(), replace=False)
        for index, choice in enumerate(choices):
            match = items.iloc[choice]["theme"] in {themes[theme], themes[second]}
            relevant = rng.random() < (0.94 if match else 0.42)
            feedback = (rng.uniform(0.74, 1) if relevant else rng.uniform(0.02, 0.33))
            if config.positive > 1:
                feedback = 1 + 4 * feedback
            timestamp = start + timedelta(days=number + int(index) * 7, hours=number % 24)
            interactions.append((f"demo-{number + 1:03d}", items.iloc[choice]["item_id"], timestamp, feedback))
    events = pd.DataFrame(interactions, columns=["user_id", "item_id", "timestamp", "feedback"])
    return clean(Dataset(items, events, demo=True), config, filter_interactions=False)


def data_root() -> Path:
    return Path(os.getenv("RECO_DATA_DIR", "data/processed"))


def checksum(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def write_dataset(dataset: Dataset, directory: Path, source: str) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    tables = {"items.parquet": dataset.items, "interactions.parquet": dataset.interactions}
    manifest = {
        "format": FORMAT_VERSION, "source": source, "temporal": dataset.temporal, "demo": dataset.demo,
        "demo_version": DEMO_VERSION if dataset.demo else None, "files": {},
    }
    versions = directory / ".versions"
    versions.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        pending = Path(temporary)
        version = pending / "parquet"
        version.mkdir()
        for name, table in tables.items():
            path = version / name
            table.to_parquet(path, index=False)
            manifest["files"][name] = {"sha256": checksum(path), "rows": len(table)}
        generation = hashlib.sha256(
            "".join(meta["sha256"] for meta in manifest["files"].values()).encode()
        ).hexdigest()[:24]
        target = versions / generation
        try:
            version.rename(target)
        except OSError:
            # An identical concurrent import may already have committed this generation.
            if not all((target / name).is_file() and checksum(target / name) == metadata["sha256"]
                       for name, metadata in manifest["files"].items()):
                raise
        for name, metadata in manifest["files"].items():
            metadata["path"] = f".versions/{generation}/{name}"
        next_manifest = pending / "manifest.json"
        next_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        next_manifest.replace(directory / "manifest.json")
    return manifest


def read_dataset(config: DomainConfig, directory: Path | None = None) -> Dataset:
    root = (directory or data_root()) / config.slug
    manifest_file = root / "manifest.json"
    if not manifest_file.exists():
        if root.exists() and any(root.glob("*.parquet")):
            raise ValueError(f"Manifeste absent pour le domaine {config.slug}.")
        if config.slug not in demo_catalog():
            raise FileNotFoundError(f"Importez les données du domaine {config.slug} avec reco-platform ingest.")
        return demo_dataset(config)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT_VERSION:
        raise ValueError(f"Format de données incompatible pour {config.slug}.")
    paths = {}
    for name in ("items.parquet", "interactions.parquet"):
        entry = manifest["files"][name]
        filename = entry.get("path", name)
        if filename != name and not re.fullmatch(r"\.versions/[0-9a-f]{24}/" + re.escape(name), filename):
            raise ValueError(f"Chemin invalide dans le manifeste de {config.slug}.")
        paths[name] = root / filename
        if checksum(paths[name]) != entry["sha256"]:
            raise ValueError(f"Empreinte incorrecte : {paths[name]}. Régénérez les fichiers avec ingest.")
    dataset = Dataset(pd.read_parquet(paths["items.parquet"]), pd.read_parquet(paths["interactions.parquet"]),
                      temporal=manifest["temporal"], demo=manifest["demo"])
    return clean(dataset, config, filter_interactions=False)
