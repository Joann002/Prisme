"""Catalogue public mis en mémoire au démarrage, sans transmettre les favoris."""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import pandas as pd

LOGGER = logging.getLogger(__name__)
USER_AGENT = "Prisme/0.1 (https://github.com/Joann002/Prisme)"
MAX_RESPONSE = 2_000_000

FILMS = {
    "Dune (film, 2021)": ("Science-fiction", "Espace"),
    "Interstellar": ("Science-fiction", "Espace"),
    "Inception": ("Science-fiction", "Rêves", "Thriller"),
    "Seul sur Mars (film)": ("Science-fiction", "Mars", "Survie"),
    "Avatar (film, 2009)": ("Science-fiction", "Espace", "Aventure"),
    "2001, l'Odyssée de l'espace": ("Science-fiction", "Espace", "Intelligence artificielle"),
    "Le Cinquième Élément": ("Science-fiction", "Espace", "Aventure"),
    "Le Labyrinthe de Pan": ("Fantasy", "Fantastique", "Conte"),
    "Le Voyage de Chihiro": ("Fantasy", "Animation", "Voyage"),
    "Premier Contact (film)": ("Science-fiction", "Extra-terrestres", "Langage"),
    "Blade Runner (film)": ("Science-fiction", "Cyberpunk", "Intelligence artificielle"),
    "Alien, le huitième passager": ("Science-fiction", "Espace", "Horreur"),
    "Annihilation (film)": ("Science-fiction", "Mystère", "Horreur"),
    "Gravity (film)": ("Science-fiction", "Espace", "Survie"),
    "Matrix (film)": ("Science-fiction", "Cyberpunk", "Action"),
    "Minority Report (film)": ("Science-fiction", "Thriller", "Enquête"),
    "Eternal Sunshine of the Spotless Mind": ("Science-fiction", "Romance", "Mémoire"),
    "Retour vers le futur": ("Science-fiction", "Comédie", "Voyage dans le temps"),
    "Her (film)": ("Science-fiction", "Romance", "Intelligence artificielle"),
    "Wall-E": ("Science-fiction", "Animation", "Espace"),
    "La Famille Bélier": ("Comédie", "Musique", "Famille"),
    "Les Évadés (film, 1994)": ("Drame", "Amitié", "Prison"),
    "À couteaux tirés (film, 2019)": ("Enquête", "Mystère", "Comédie"),
    "La Haine": ("Drame", "France", "Société"),
    "Les Aventuriers de l'arche perdue": ("Aventure", "Archéologie", "Action"),
}
RECIPES = {
    "Penne arrabbiata": ("Pâtes", "Italie", "Épicé"),
    "Pâtes aux champignons": ("Pâtes", "Champignons", "Végétarien"),
    "Pâtes aux tomates et épinards": ("Pâtes", "Tomate", "Végétarien"),
    "Boulettes de millet": ("Végétarien", "Céréales"),
    "Khao soy": ("Nouilles", "Thaïlande", "Épicé"),
    "Ratatouille": ("Légumes", "Provence", "Végétarien"),
    "Couscous": ("Céréales", "Maghreb", "Épices"),
    "Tajine": ("Maroc", "Épices"),
    "Falafel": ("Pois chiches", "Moyen-Orient", "Végétarien"),
    "Tiramisu": ("Dessert", "Café", "Italie"),
    "Crêpes": ("Dessert", "France"),
    "Gâteau au chocolat": ("Dessert", "Chocolat", "Pâtisserie"),
    "Pâtes à la carbonara": ("Pâtes", "Italie"),
    "Gaspacho": ("Soupe", "Tomate", "Espagne"),
    "Taboulé": ("Salade", "Moyen-Orient", "Céréales"),
    "Guacamole": ("Avocat", "Mexique", "Végétarien"),
    "Pesto": ("Basilic", "Italie", "Végétarien"),
}

GENRES = {
    "science fiction": "Science-fiction",
    "sci-fi": "Science-fiction",
    "hard science fiction": "Science-fiction",
    "space": "Espace",
    "space opera": "Espace",
    "extraterrestrial beings": "Extra-terrestres",
    "robots": "Robots",
    "fantasy fiction": "Fantasy",
    "mystery": "Mystère",
    "mystery and detective stories": "Enquête",
    "detective and mystery stories": "Enquête",
    "soundtrack": "Bande originale",
    "electronic": "Électronique",
    "classical": "Classique",
    "instrumental": "Instrumental",
    "strategy": "Stratégie",
    "shooter": "Tir",
}


def fetch_json(url, **params):
    request = Request(
        f"{url}?{urlencode(params)}" if params else url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    for attempt in range(2):
        try:
            with urlopen(request, timeout=5) as response:
                raw = response.read(MAX_RESPONSE + 1)
            break
        except HTTPError as exc:
            delay = exc.headers.get("Retry-After", "1")
            if attempt or exc.code not in {429, 502, 503, 504} or not delay.isdecimal() or int(delay) > 4:
                raise
            time.sleep(max(1, int(delay)))
    if len(raw) > MAX_RESPONSE:
        raise ValueError("Réponse de catalogue trop volumineuse.")
    return json.loads(raw)


def text(value, limit=500):
    return " ".join(value.split())[:limit] if isinstance(value, str) else ""


def https(value):
    value = text(value, 2048)
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    return value if parsed.scheme == "https" and parsed.hostname and not parsed.username else ""


def tags(values):
    normalized = (GENRES.get(value.casefold(), value) for value in map(text, values) if value)
    return ", ".join(dict.fromkeys(normalized))[:420]


def item(identifier, titre, description, genres, source, source_url, *, image="", year=""):
    return {
        "item_id": identifier,
        "titre": text(titre, 180),
        "description": text(description, 500),
        "tags": tags(genres),
        "source": source,
        "source_url": https(source_url),
        "image": https(image),
        "year": str(year) if re.fullmatch(r"\d{4}", str(year)) else "",
    }


def wiki(host, source, prefix, titles):
    reply = fetch_json(
        f"https://{host}/w/api.php", action="query", titles="|".join(prefix + title for title in titles),
        redirects=1, prop="info|extracts", inprop="url", exintro=1, explaintext=1, exchars=420,
        exlimit="max", format="json", formatversion=2,
    )
    query = reply["query"]
    genres_by_title = {prefix + title: genres for title, genres in titles.items()}
    for redirect in query.get("redirects", []):
        if redirect["from"] in genres_by_title:
            genres_by_title[redirect["to"]] = genres_by_title[redirect["from"]]
    for page in query["pages"]:
        if page.get("missing") or not page.get("pageid"):
            continue
        title = page["title"]
        clean_title = re.sub(r"\s*\(film(?:, \d{4})?\)$", "", title.removeprefix(prefix))
        description = page.get("extract") or (
            "Recette du livre de cuisine de Wikilivres." if prefix else "Fiche de film sur Wikipédia."
        )
        if source == "Wikilivres":
            description = "Recette du livre de cuisine de Wikilivres."
        url = page["fullurl"]
        if page.get("lastrevid"):
            url = f"{url}?{urlencode({'oldid': page['lastrevid']})}"
        year = re.search(r"\(film, ((?:18|19|20)\d{2})\)$", title)
        yield item(
            f"wiki-{page['pageid']}", clean_title, description,
            genres_by_title.get(title, ()), source, url, year=year.group(1) if year else "",
        )


def movies():
    return wiki("fr.wikipedia.org", "Wikipédia", "", FILMS)


def recipes():
    return wiki("fr.wikibooks.org", "Wikilivres", "Livre de cuisine/", RECIPES)


def books():
    reply = fetch_json(
        "https://openlibrary.org/search.json",
        q="(subject:science_fiction OR subject:fantasy OR subject:mystery OR subject:music) AND language:fre",
        limit=30, fields="key,title,author_name,subject,first_publish_year,cover_i",
    )
    for work in reply["docs"]:
        key = work.get("key", "").removeprefix("/works/")
        if not re.fullmatch(r"OL\d+W", key):
            continue
        authors = ", ".join(map(text, (work.get("author_name") or [])[:3]))
        subjects = list(dict.fromkeys((work.get("subject") or [])[:14]))
        cover = work.get("cover_i")
        image = f"https://covers.openlibrary.org/b/id/{cover}-M.jpg?default=false" if type(cover) is int else ""
        yield item(
            f"ol-{key}", work.get("title"), f"Par {authors}." if authors else "", subjects,
            "Open Library", f"https://openlibrary.org/works/{key}",
            image=image, year=work.get("first_publish_year", ""),
        )


def games():
    reply = fetch_json("https://www.freetogame.com/api/games", category="sci-fi")
    for game in reply[:30]:
        if type(game.get("id")) is not int:
            continue
        yield item(
            f"ftg-{game['id']}", game.get("title"), game.get("short_description"),
            ("Science-fiction", game.get("genre"), game.get("platform")), "FreeToGame",
            game.get("freetogame_profile_url"), image=game.get("thumbnail"),
            year=text(game.get("release_date"))[:4],
        )


def music():
    reply = fetch_json(
        "https://musicbrainz.org/ws/2/release-group/", fmt="json", limit=25,
        query='(tag:"science fiction" OR tag:jazz OR secondarytype:soundtrack) AND primarytype:album',
    )
    for album in reply["release-groups"]:
        identifier = album.get("id", "")
        if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", identifier):
            continue
        credits = ", ".join(text(artist.get("name")) for artist in album.get("artist-credit", [])[:3])
        genres = [tag.get("name") for tag in album.get("tags", [])[:10]]
        genres.extend(album.get("secondary-types", []))
        yield item(
            f"mb-{identifier}", album.get("title"), f"Album de {credits}." if credits else "Album.",
            genres, "MusicBrainz", f"https://musicbrainz.org/release-group/{identifier}",
            year=text(album.get("first-release-date"))[:4],
        )


PROVIDERS = {"movies": movies, "books": books, "games": games, "music": music, "recipes": recipes}


def title_key(title):
    value = unicodedata.normalize("NFKD", title.casefold())
    return re.sub(r"[^\w]+", " ", "".join(char for char in value if not unicodedata.combining(char))).strip()


def enrich(dataset, slug, entries):
    rows = dataset.items.to_dict("records")
    by_title = {}
    for row in rows:
        by_title.setdefault(title_key(row["titre"]), []).append(row)
    ids = {row["item_id"] for row in rows}
    for entry in entries:
        if not entry["titre"] or not entry["source_url"] or entry["item_id"] in ids:
            continue
        key = title_key(entry["titre"])
        matches = [row for row in by_title.get(key, []) if (
            not row["year"] or not entry["year"] or row["year"] == entry["year"]
        )]
        if len(matches) == 1:
            row = matches[0]
            for field in ("description", "tags", "source", "source_url", "image", "year"):
                if not row.get(field):
                    row[field] = entry[field]
        elif not matches:
            row = {**entry, "domaine": slug}
            rows.append(row)
            ids.add(row["item_id"])
            by_title.setdefault(key, []).append(row)
    return replace(dataset, items=pd.DataFrame(rows).fillna(""))


def load_external(datasets):
    def load_one(slug, provider):
        try:
            entries = list(provider())
            if not entries:
                raise ValueError("Catalogue vide")
            return enrich(datasets[slug], slug, entries)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            LOGGER.warning("Catalogue externe indisponible pour %s (%s).", slug,
                           getattr(exc, "code", type(exc).__name__))
            return datasets[slug]

    active = [(slug, PROVIDERS[slug]) for slug, dataset in datasets.items() if dataset.demo and slug in PROVIDERS]
    if not active:
        return datasets
    with ThreadPoolExecutor(max_workers=len(active)) as pool:
        updates = pool.map(lambda pair: (pair[0], load_one(*pair)), active)
        return {**datasets, **dict(updates)}
