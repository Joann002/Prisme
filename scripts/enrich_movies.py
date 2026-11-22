"""Enrichit un échantillon MovieLens via TMDB avec un jeton autorisé."""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def describe(tmdb_id, token):
    request = Request(
        f"https://api.themoviedb.org/3/movie/{tmdb_id}?language=fr-FR",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return {}
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()
    token = os.getenv("TMDB_TOKEN")
    if not token or not 1 <= args.limit <= 500:
        parser.error("Un TMDB_TOKEN et une limite comprise entre 1 et 500 sont nécessaires.")
    target = args.directory / "metadata.csv"
    metadata = {}
    if target.exists():
        with target.open(encoding="utf-8") as source:
            metadata = {row["item_id"]: row for row in csv.DictReader(source)}
    with (args.directory / "links.csv").open(encoding="utf-8") as source:
        candidates = [row for row in csv.DictReader(source)
                      if row["tmdbId"].isdigit() and row["movieId"] not in metadata][:args.limit]
    for row in candidates:
        info = describe(row["tmdbId"], token)
        poster = info.get("poster_path")
        metadata[row["movieId"]] = {
            "item_id": row["movieId"], "description": info.get("overview", ""),
            "image": f"https://image.tmdb.org/t/p/w500{poster}" if poster else "",
        }
        time.sleep(.26)
    pending = target.with_suffix(".tmp")
    with pending.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["item_id", "description", "image"])
        writer.writeheader()
        writer.writerows(metadata.values())
    pending.replace(target)
    print(f"{len(metadata)} lignes écrites. Appliquez les conditions d’attribution TMDB avant diffusion.")


if __name__ == "__main__":
    main()
