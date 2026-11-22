import pandas as pd

from .base import Dataset, DomainAdapter, csv


class SteamAdapter(DomainAdapter):
    def read(self, root):
        items = csv(root, "games.csv", dtype={"appid": str}).rename(
            columns={"appid": "item_id", "name": "titre", "header_image": "image", "genres": "tags",
                     "short_description": "description"}
        )
        items["description"] = items.get("description", "")
        items["tags"] = items.get("tags", "")
        events = csv(root, "reviews.csv", dtype={"appid": str, "steamid": str}).rename(
            columns={"appid": "item_id", "steamid": "user_id"}
        )
        events["timestamp"] = events.get("timestamp_created", events.get("timestamp", pd.NaT))
        if "voted_up" in events:
            events["feedback"] = events["voted_up"].astype(str).str.lower().map(
                {"true": 1, "false": 0, "1": 1, "0": 0}
            )
        else:
            events["feedback"] = pd.to_numeric(events["playtime_forever"], errors="coerce").clip(0, 60) / 60
        return Dataset(self.items(items), events)
