import numpy as np
import pandas as pd

from .base import Dataset, DomainAdapter, csv


class LastFMAdapter(DomainAdapter):
    def read(self, root):
        artists = csv(root, "artists.csv", dtype={"artist_id": str}).rename(
            columns={"artist_id": "item_id", "name": "titre"}
        )
        artists["description"] = artists.get("description", "")
        artists["tags"] = artists.get("tags", "")
        plays = csv(root, "listens.csv", dtype={"artist_id": str, "user_id": str}).rename(
            columns={"artist_id": "item_id"}
        )
        counts = pd.to_numeric(plays["plays"], errors="coerce").clip(0, None)
        plays["feedback"] = np.log1p(counts).clip(0, 5) / 5
        temporal = "timestamp" in plays
        if not temporal:
            plays["timestamp"] = pd.NaT
        return Dataset(self.items(artists), plays, temporal=temporal)
