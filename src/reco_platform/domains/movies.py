import pandas as pd

from .base import Dataset, DomainAdapter, csv


class MovieLensAdapter(DomainAdapter):
    def read(self, root):
        items = csv(root, "movies.csv", dtype={"movieId": str}).rename(
            columns={"movieId": "item_id", "title": "titre", "genres": "tags"}
        )
        items["year"] = items["titre"].str.extract(r"\((\d{4})\)\s*$")[0]
        items["titre"] = items["titre"].str.replace(r"\s*\(\d{4}\)\s*$", "", regex=True)
        items["tags"] = items["tags"].replace("(no genres listed)", "").str.replace("|", ", ", regex=False)
        items["description"] = ""
        if (root / "tags.csv").is_file():
            tags = csv(root, "tags.csv", dtype={"movieId": str}).dropna(subset=["tag"])
            community = tags.groupby("movieId")["tag"].agg(lambda values: " ".join(pd.unique(values)))
            items["description"] = items["item_id"].map(community)
        if (root / "metadata.csv").is_file():
            metadata = csv(root, "metadata.csv", dtype={"item_id": str})
            lookup = metadata.drop_duplicates("item_id", keep="last").set_index("item_id")
            items["description"] = items["item_id"].map(lookup["description"]).fillna(items["description"])
            if "image" in lookup:
                items["image"] = items["item_id"].map(lookup["image"])
        ratings = csv(root, "ratings.csv", dtype={"movieId": str, "userId": str}).rename(
            columns={"movieId": "item_id", "userId": "user_id", "rating": "feedback"}
        )
        return Dataset(self.items(items), ratings)
