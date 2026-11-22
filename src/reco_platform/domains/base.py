from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd

from reco_platform.config import DomainConfig

INTERACTION_COLUMNS = ["user_id", "item_id", "timestamp", "feedback"]
ITEM_COLUMNS = ["item_id", "titre", "description", "tags", "domaine"]
OPTIONAL_COLUMNS = ["image", "year", "theme", "entity"]


@dataclass
class Dataset:
    items: pd.DataFrame
    interactions: pd.DataFrame
    temporal: bool = True
    demo: bool = False


class DomainAdapter(ABC):
    def __init__(self, config: DomainConfig):
        self.config = config

    @abstractmethod
    def read(self, root: Path) -> Dataset:
        """Convertit les données sources vers le schéma commun."""

    def items(self, frame: pd.DataFrame) -> pd.DataFrame:
        return frame.assign(domaine=self.config.slug)

    def load(self, root: Path, *, filter_interactions: bool = True) -> Dataset:
        dataset = self.read(root)
        return clean(dataset, self.config, filter_interactions=filter_interactions)


def adapter_for(config: DomainConfig) -> DomainAdapter:
    module, _, name = config.adapter.partition(":")
    if not name:
        raise ValueError("L’adaptateur doit être au format module:Classe.")
    adapter = getattr(import_module(module), name)
    if not issubclass(adapter, DomainAdapter):
        raise TypeError(f"{config.adapter} doit hériter de DomainAdapter.")
    return adapter(config)


def csv(root: Path, filename: str, **kwargs) -> pd.DataFrame:
    path = root / filename
    if not path.is_file():
        raise FileNotFoundError(f"Fichier source manquant : {path}")
    return pd.read_csv(path, **kwargs)


def utc(series: pd.Series) -> pd.Series:
    numbers = pd.to_numeric(series, errors="coerce")
    dates = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns, UTC]")
    is_number = numbers.notna()
    for unit, mask in (
        ("s", is_number & numbers.abs().lt(1e11)),
        ("ms", is_number & numbers.abs().ge(1e11) & numbers.abs().lt(1e14)),
        ("us", is_number & numbers.abs().ge(1e14) & numbers.abs().lt(1e17)),
        ("ns", is_number & numbers.abs().ge(1e17)),
    ):
        dates.loc[mask] = pd.to_datetime(numbers[mask], unit=unit, utc=True, errors="coerce")
    dates.loc[~is_number] = pd.to_datetime(series[~is_number], utc=True, errors="coerce", format="mixed")
    return dates


def clean(dataset: Dataset, config: DomainConfig, *, filter_interactions: bool = True) -> Dataset:
    items = dataset.items.loc[:, ITEM_COLUMNS + [
        name for name in OPTIONAL_COLUMNS if name in dataset.items
    ]].copy()
    interactions = dataset.interactions.loc[:, INTERACTION_COLUMNS].copy()
    for frame, columns in ((items, ["item_id", "titre"]), (interactions, ["item_id", "user_id"])):
        for column in columns:
            frame[column] = frame[column].astype("string").str.strip().replace("", pd.NA)
    items = items.dropna(subset=["item_id", "titre"]).copy()
    interactions = interactions.dropna(subset=["item_id", "user_id"]).copy()
    for column in ["description", "tags", *OPTIONAL_COLUMNS]:
        if column not in items:
            items[column] = ""
        items[column] = items[column].fillna("").astype(str).str.strip()
    items["domaine"] = config.slug
    items = items.drop_duplicates("item_id", keep="last").sort_values("item_id").reset_index(drop=True)
    interactions["feedback"] = pd.to_numeric(interactions["feedback"], errors="coerce")
    interactions = interactions.loc[np.isfinite(interactions["feedback"])].copy()
    interactions["timestamp"] = utc(interactions["timestamp"])
    if dataset.temporal:
        interactions = interactions.dropna(subset=["timestamp"])
    interactions = interactions[interactions["item_id"].isin(items["item_id"])]
    interactions = (
        interactions.sort_values("timestamp", kind="stable", na_position="first")
        .drop_duplicates(["user_id", "item_id"], keep="last")
    )
    if filter_interactions:
        interactions = frequency_filter(interactions, config.min_user, config.min_item)
    return Dataset(items, interactions.reset_index(drop=True), dataset.temporal, dataset.demo)


def frequency_filter(interactions: pd.DataFrame, min_user: int, min_item: int) -> pd.DataFrame:
    while not interactions.empty:
        users = interactions.groupby("user_id")["item_id"].transform("size").ge(min_user)
        items = interactions.groupby("item_id")["user_id"].transform("size").ge(min_item)
        if (users & items).all():
            break
        interactions = interactions.loc[users & items]
    return interactions
