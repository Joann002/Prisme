# Fiches des données

Les schémas d’import sont documentés ci-dessous. Télécharge les sources auprès de leurs producteurs et vérifie leur version et leurs conditions avant chaque nouveau partage ou usage commercial. Les données brutes et les Parquet externes restent en dehors du dépôt.

| Domaine | Fichiers d’entrée et champs | Usage et limites |
| --- | --- | --- |
| Démonstration | Catalogue rédactionnel dans le dépôt, avec 150 profils synthétiques stables et 5 645 interactions simulées | Origine et graine documentées. Les associations culturelles sont annotées pour l’étude cross-domain. Les lectures, avis et notes simulés ne représentent aucune personne réelle. Les visuels d’ambiance sont générés et illustratifs. |
| Films | MovieLens `movies.csv(movieId,title,genres)`, `ratings.csv(userId,movieId,rating,timestamp)`, `tags.csv` facultatif. L’enrichissement facultatif lit `metadata.csv(item_id,description,image)`. | Notes de volontaires, couverture variable des films et tags en anglais. MovieLens impose notamment des restrictions sur la redistribution et l’usage commercial. Voir les conditions de la version téléchargée. [MovieLens](https://grouplens.org/datasets/movielens/latest/) · [TMDB](https://developer.themoviedb.org/docs/faq) |
| Livres | Goodbooks-10k `books.csv(book_id,title,authors,original_publication_year)`, `ratings.csv(user_id,book_id,rating)`, fichiers de tags facultatifs. Un `metadata.csv(item_id,description)` peut enrichir le catalogue. | Priorité aux livres populaires. Les notes originales n’ont pas de dates. Elles servent au classement, et une source horodatée indépendante est requise pour l’évaluation temporelle. Le dépôt indique CC BY-SA 4.0 pour les données. Les couvertures et métadonnées enrichies ont leurs propres conditions. [Goodbooks-10k](https://github.com/zygmuntz/goodbooks-10k) · [Open Library](https://openlibrary.org/developers/api) |
| Jeux | Export autorisé du Steam Store `games.csv(appid,name,genres,short_description,header_image)` et `reviews.csv(appid,steamid,timestamp_created,voted_up)`. Variante durée avec `playtime_forever` en minutes. | Les achats, le temps de jeu et les avis sont des signaux différents. Les avis sont auto-sélectionnés. Remplace les identifiants Steam par des clés de recherche internes avant l’import, sans exporter les textes d’avis ni les profils. [Steam Store Reviews](https://partner.steamgames.com/doc/store/getreviews) · [Conditions de l’API Steam](https://steamcommunity.com/dev/apiterms) |
| Musique | Export autorisé Last.fm ou équivalent `artists.csv(artist_id,name,tags,description)` et `listens.csv(user_id,artist_id,plays,timestamp)`. Pour des comptes agrégés sans dates, le classement reste disponible. | Les écoutes répétées sont comprimées par `log1p` et reflètent aussi l’exposition. Consulte la licence propre à l’export. L’API Last.fm et les enrichissements MusicBrainz obéissent à leurs conditions respectives. [Last.fm](https://www.last.fm/api/tos) · [MusicBrainz](https://musicbrainz.org/doc/MusicBrainz_Database/License) |
| Recettes | Food.com `RAW_recipes.csv(id,name,description,tags)`, `RAW_interactions.csv(user_id,recipe_id,date,rating)`. La note 0 est écartée. | Les évaluations et dates proviennent des comptes de la plateforme. Vérifie la licence exacte et les restrictions de la fiche Kaggle avant publication. [Food.com sur Kaggle](https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions) |

## Import

```bash
python scripts/download_data.py movies --accept-terms
uv run --no-sync reco-platform ingest movies data/raw/movies
uv run --no-sync reco-platform benchmark --output reports/local
```

Le script prend aussi en charge `books` et `recipes`. Pour ce dernier, configure le client Kaggle avec tes propres identifiants. Fournis des exports autorisés en CSV pour Steam et Last.fm. L’enrichissement MovieLens facultatif utilise `python scripts/enrich_movies.py data/raw/movies` et la variable `TMDB_TOKEN`. Consulte les exigences d’attribution TMDB avant de diffuser un catalogue enrichi.

Un import produit deux tables Parquet et un manifeste avec source, nombre de lignes, version du format et empreintes SHA-256. Le modèle élimine les profils et les éléments trop rares sur les interactions d’entraînement. Il conserve les métadonnées des éléments peu observés pour permettre la recommandation par contenu. Les catalogues importés et la démo peuvent coexister. Chaque ligne du benchmark indique la provenance.

Pour évaluer des relations externes entre domaines, fournis un CSV de référence avec `source_domain,source_id,target_domain,target_id` via `--relations`.

Pour reproduire la mesure externe fournie pour MovieLens seul, copie `src/reco_platform/configs/movies.yaml` dans un répertoire de configuration distinct. Exécute ensuite `reco-platform benchmark` avec `RECO_CONFIG_DIR` pointant vers ce répertoire et `--data` vers le répertoire de Parquet exportés.

Les Parquet synthétiques versionnés sont dans `data/demo`. Pour les utiliser tels quels, passe `--data data/demo` au benchmark ou définis `RECO_DATA_DIR=data/demo` avant de démarrer le service.
