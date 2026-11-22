import pandas as pd

from .base import Dataset, DomainAdapter, csv


class FoodAdapter(DomainAdapter):
    def read(self, root):
        items = csv(root, "RAW_recipes.csv", dtype={"id": str}).rename(
            columns={"id": "item_id", "name": "titre"}
        )
        items["tags"] = items["tags"].str.replace(r"[\[\]'\"\-]", " ", regex=True)
        interactions = csv(root, "RAW_interactions.csv", dtype={"recipe_id": str, "user_id": str}).rename(
            columns={"recipe_id": "item_id", "date": "timestamp", "rating": "feedback"}
        )
        interactions = interactions.loc[pd.to_numeric(interactions["feedback"], errors="coerce").gt(0)]
        return Dataset(self.items(items), interactions)
