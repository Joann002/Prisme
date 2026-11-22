"""Télécharge les sources publiques ou convertit les exports autorisés."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
from zipfile import ZipFile

MOVIELENS = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
GOODBOOKS = "https://raw.githubusercontent.com/zygmuntz/goodbooks-10k/master"
GOODBOOKS_FILES = ("books.csv", "ratings.csv", "book_tags.csv", "tags.csv")
FOOD_DATASET = "shuyangli94/food-com-recipes-and-user-interactions"


def fetch(url, destination):
    request = Request(url, headers={"User-Agent": "Prisme/0.1 (dataset importer)"})
    with urlopen(request, timeout=90) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def unpack(source, destination, wanted):
    with ZipFile(source) as bundle:
        matches = {PurePosixPath(member.filename).name: member
                   for member in bundle.infolist() if not member.is_dir()}
        for name in wanted:
            with bundle.open(matches[name]) as data, (destination / name).open("wb") as output:
                shutil.copyfileobj(data, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=["movies", "books", "recipes"])
    parser.add_argument("--directory", type=Path, default=Path("data/raw"))
    parser.add_argument("--accept-terms", action="store_true", help="Confirme avoir lu les CGU de la source.")
    args = parser.parse_args()
    if not args.accept_terms:
        parser.error("Consultez les liens dans docs/datasets.md, puis utilisez --accept-terms.")
    args.directory.mkdir(parents=True, exist_ok=True)
    target = args.directory / args.source
    if target.exists():
        parser.error(f"Le répertoire {target} existe déjà.")
    with tempfile.TemporaryDirectory(dir=args.directory) as directory:
        temp = Path(directory)
        files = temp / "files"
        files.mkdir()
        if args.source == "movies":
            archive = temp / "movielens.zip"
            fetch(MOVIELENS, archive)
            unpack(archive, files, ("movies.csv", "ratings.csv", "tags.csv", "links.csv", "README.txt"))
        elif args.source == "books":
            for filename in GOODBOOKS_FILES:
                fetch(f"{GOODBOOKS}/{filename}", files / filename)
        else:
            executable = shutil.which("kaggle")
            if executable is None:
                parser.error("L’outil Kaggle doit être installé et configuré pour récupérer Food.com.")
            subprocess.run([executable, "datasets", "download", "-d", FOOD_DATASET, "-p", str(temp)],
                           check=True, env=os.environ.copy())
            archive = next(temp.glob("*.zip"))
            unpack(archive, files, ("RAW_recipes.csv", "RAW_interactions.csv"))
        files.rename(target)
    print(target)


if __name__ == "__main__":
    main()
