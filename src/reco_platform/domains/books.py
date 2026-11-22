import pandas as pd

from .base import Dataset, DomainAdapter, csv


class GoodbooksAdapter(DomainAdapter):
    def read(self, root):
        books = csv(root, "books.csv", dtype={"book_id": str}).rename(
            columns={"book_id": "item_id", "title": "titre", "image_url": "image"}
        )
        books["year"] = ""
        if "original_publication_year" in books:
            books["year"] = (pd.to_numeric(books["original_publication_year"], errors="coerce")
                             .fillna(0).astype(int).replace(0, "").astype(str))
        books["description"] = books.get("description", books.get("authors", ""))
        books["tags"] = books.get("tags", "")
        if (root / "book_tags.csv").is_file() and (root / "tags.csv").is_file():
            book_tags = csv(root, "book_tags.csv", dtype={"goodreads_book_id": str})
            tags = csv(root, "tags.csv")
            top = (book_tags.sort_values("count", ascending=False, kind="stable")
                   .merge(tags, on="tag_id").dropna(subset=["tag_name"])
                   .groupby("goodreads_book_id").head(8))
            names = top.groupby("goodreads_book_id")["tag_name"].agg(", ".join)
            books["tags"] = books["goodreads_book_id"].astype(str).map(names).fillna(books["tags"])
        if (root / "metadata.csv").is_file():
            meta = csv(root, "metadata.csv", dtype={"item_id": str}).drop_duplicates("item_id", keep="last")
            books["description"] = books["item_id"].map(meta.set_index("item_id")["description"]).fillna(
                books["description"]
            )
        ratings = csv(root, "ratings.csv", dtype={"book_id": str, "user_id": str}).rename(
            columns={"book_id": "item_id", "rating": "feedback"}
        )
        temporal = "timestamp" in ratings
        if not temporal:
            ratings["timestamp"] = pd.NaT
        return Dataset(self.items(books), ratings, temporal=temporal)
