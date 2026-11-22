from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from reco_platform.config import MODEL_LABELS, DomainConfig, load_configs
from reco_platform.data import read_dataset
from reco_platform.domains.base import Dataset, frequency_filter
from reco_platform.domains.external import load_external
from reco_platform.features.content import ContentSpace, item_tags
from reco_platform.models.rankers import Collaborative, unit_scores

SEMANTIC_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class RequestError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@dataclass
class Domain:
    config: DomainConfig
    dataset: Dataset
    catalog: list[dict]
    model: Collaborative

    def __post_init__(self):
        self.items = {item["item_id"]: item for item in self.catalog}
        self.tags = [
            {tag.casefold() for tag in item_tags(item["tags"])} for item in self.catalog
        ]
        featured = self.config.parameters.get("featured", []) if self.dataset.demo else []
        order = {item: index for index, item in enumerate(featured)}
        self.ordered = sorted(self.catalog, key=lambda item: (
            order.get(item["item_id"], len(order)), -self.model.counts[self.model.item_index[item["item_id"]]],
        ))
        self.search_terms = [
            search_key(f'{item["titre"]} {item["tags"]}') for item in self.ordered
        ]


def search_key(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(char))


class Recommender:
    def __init__(self, configs: dict[str, DomainConfig], datasets: dict[str, Dataset],
                 *, semantic_model: str | None = None, include_tags: bool = True,
                 shared_users: bool = False, only: set[str] | None = None,
                 semantic_index: Path | None = None):
        self.domains = {}
        self.shared_users = shared_users
        for slug, config in configs.items():
            dataset = datasets[slug]
            catalog = dataset.items.to_dict("records")
            if not catalog:
                raise ValueError(f"Catalogue vide pour {slug}")
            requested = set(config.models) if only is None else set(only)
            if requested & {"hybrid", "advanced"}:
                requested.update(("svd", "als", "knn"))
            model = Collaborative([item["item_id"] for item in catalog],
                                  frequency_filter(dataset.interactions, config.min_user, config.min_item),
                                  config, requested)
            self.domains[slug] = Domain(config, dataset, catalog, model)
        self.content = ContentSpace({slug: domain.catalog for slug, domain in self.domains.items()},
                                    semantic_model, include_tags, semantic_index)

    @classmethod
    def load(cls, directory: Path | None = None, *, semantic_model: str | None = None,
             external_catalogs: bool | None = None):
        configs = load_configs()
        index = os.getenv("RECO_SEMANTIC_INDEX") if not semantic_model else None
        datasets = {slug: read_dataset(config, directory) for slug, config in configs.items()}
        if external_catalogs is None:
            external_catalogs = os.getenv("RECO_EXTERNAL_CATALOGS") == "1"
        # A precomputed semantic index is tied to a fixed catalogue fingerprint.
        if external_catalogs and not index:
            datasets = load_external(datasets)
        return cls(configs, datasets,
                   semantic_model=semantic_model or os.getenv("RECO_SEMANTIC_MODEL") or None,
                   shared_users=os.getenv("RECO_SHARED_USERS") == "1",
                   semantic_index=Path(index) if index else None)

    def domain(self, slug: str) -> Domain:
        if slug not in self.domains:
            raise RequestError("Domaine introuvable.", 404)
        return self.domains[slug]

    def models(self, slug: str) -> list[str]:
        domain = self.domain(slug)
        return [model for model in domain.config.models
                if domain.model.available(model) and
                (model not in {"semantic", "advanced"} or self.content.dense is not None)]

    def default_model(self, slug: str) -> str:
        domain = self.domain(slug)
        available = self.models(slug)
        if domain.config.default_model in available:
            return domain.config.default_model
        if "popular" in available:
            return "popular"
        if available:
            return available[0]
        raise RequestError("Aucun modèle disponible pour ce domaine.", 503)

    def metadata(self):
        return [{
            "slug": slug, "label": domain.config.label, "singular": domain.config.singular,
            "icon": domain.config.icon, "items": len(domain.items), "demo": domain.dataset.demo,
            "external_items": sum(bool(item.get("source_url")) for item in domain.catalog),
            "default_model": self.default_model(slug),
            "models": [{"id": model, "label": MODEL_LABELS[model]} for model in self.models(slug)],
        } for slug, domain in self.domains.items()]

    def catalog(self, slug: str, query: str = "", limit: int = 30, offset: int = 0):
        domain = self.domain(slug)
        query = search_key(query.strip())
        matches = ([item for item, terms in zip(domain.ordered, domain.search_terms) if query in terms]
                   if query else domain.ordered)
        return {"items": [self.public_item(item) for item in matches[offset:offset + limit]],
                "total": len(matches)}

    @staticmethod
    def public_item(item):
        return {**{key: item[key] for key in ("item_id", "titre", "description", "domaine", "image", "year")},
                "source": item.get("source", ""), "source_url": item.get("source_url", ""),
                "tags": list(item_tags(item["tags"]))}

    def validate_ids(self, domain, ids):
        unique = list(dict.fromkeys(ids))
        if not set(unique).issubset(domain.items):
            raise RequestError("Un ou plusieurs éléments sont introuvables dans ce domaine.", 404)
        return unique

    def recommend(self, slug: str, *, liked: list[str] | None = None, user: str | None = None,
                  model: str | None = None, k: int = 10, diversify: bool = True,
                  candidates: set[str] | None = None):
        domain = self.domain(slug)
        model = model or self.default_model(slug)
        if model not in self.models(slug):
            raise RequestError("Modèle indisponible pour ce domaine.", 422)
        collaborative = domain.model
        ids = self.validate_ids(domain, liked or []) if liked is not None else collaborative.histories.get(
            user, []
        )[-15:]
        excluded = set(ids)
        if user is not None:
            excluded |= collaborative.seen.get(user, set())
        sources = [(slug, item_id) for item_id in ids]
        semantic = model in {"semantic", "advanced"}
        content = self.content.score(sources, slug, semantic=semantic)
        if model in {"popular", "random"}:
            scores = collaborative.score(model, ids, user)
        elif not sources:
            scores = collaborative.popularity
        elif model in {"tfidf", "semantic"}:
            scores = content
        elif model in {"hybrid", "advanced"}:
            ranker = next((name for name in ("als", "svd", "knn") if collaborative.available(name)), "popular")
            affinity = unit_scores(collaborative.score(ranker, ids, user))
            weight = float(domain.config.parameters.get("hybrid_weight", 0.68))
            content = unit_scores(content)
            scores = weight * content + (1 - weight) * affinity
            new_items = collaborative.counts == 0
            scores[new_items] = content[new_items]
        else:
            scores = unit_scores(collaborative.score(model, ids, user))
        if not np.any(scores):
            scores = collaborative.popularity
        explain_sources = sources if model not in {"random", "popular"} else []
        fallback = "Découverte dans ce domaine" if candidates is not None else "Populaire dans ce domaine"
        if model == "random":
            fallback = "Aléatoire"
        return self._rank(domain, scores, explain_sources, excluded, k, diversify, candidates, semantic, fallback)

    def has_shared_users(self, source, target):
        return (source.dataset.demo and target.dataset.demo) or (
            self.shared_users and not source.dataset.demo and not target.dataset.demo
        )

    def cross_recommend(self, source_slug: str, target_slug: str, liked: list[str], *,
                        method="hybrid", k=10, diversify=True, candidates: set[str] | None = None):
        if source_slug == target_slug:
            raise RequestError("Choisis deux domaines différents.", 422)
        source, target = self.domain(source_slug), self.domain(target_slug)
        ids = self.validate_ids(source, liked)
        if not ids:
            raise RequestError("Sélectionne au moins un élément de départ.", 422)
        sources = [(source_slug, item) for item in ids]
        semantic = method != "tfidf" and self.content.dense is not None
        scores = unit_scores(self.content.score(sources, target_slug, semantic=semantic))
        if method == "hybrid" and self.has_shared_users(source, target):
            affinity = unit_scores(target.model.transfer_from(source.model, ids))
            scores = 0.8 * scores + 0.2 * affinity if np.any(affinity) else scores
        if not np.any(scores):
            scores = target.model.popularity
        fallback = "Découverte dans ce domaine" if candidates is not None else "Populaire dans ce domaine"
        return self._rank(target, scores, sources, set(), k, diversify, candidates, semantic, fallback)

    def recommend_feed(self, favorites: dict[str, list[str]], *, k: int = 4):
        selected = {slug: self.validate_ids(self.domain(slug), favorites[slug]) for slug in sorted(favorites)}
        if sum(map(len, selected.values())) < 3:
            raise RequestError("Ajoute au moins trois favoris pour composer ta sélection.", 422)

        groups = {}
        for target, domain in self.domains.items():
            excluded = set(selected.get(target, ()))
            external = {record["item_id"] for record in domain.catalog if record.get("source_url")}
            candidates = external if len(external - excluded) >= k else None
            weights = {}
            best_matches = {}
            for source, liked in selected.items():
                depth = k * 3 + len(excluded)
                ranks = (self.recommend(target, liked=liked, k=depth, candidates=candidates)
                         if source == target else
                         self.cross_recommend(source, target, liked, k=depth, candidates=candidates))
                # Fuse ranks from different models and catalogues without comparing their raw scores.
                for rank, match in enumerate(ranks, start=1):
                    item_id = match["item_id"]
                    if item_id in excluded:
                        continue
                    weights[item_id] = weights.get(item_id, 0.0) + 1 / (10 + rank)
                    if item_id not in best_matches or rank < best_matches[item_id][0]:
                        best_matches[item_id] = (rank, match)
            if not weights:
                groups[target] = []
                continue
            ranked = sorted(weights, key=lambda item_id: (-weights[item_id], best_matches[item_id][0], item_id))
            peak = weights[ranked[0]]
            groups[target] = [
                {**best_matches[item_id][1], "score": round(weights[item_id] / peak, 5)} for item_id in ranked[:k]
            ]
        return groups

    def similar(self, slug: str, item_id: str, *, k=10):
        method = "semantic" if "semantic" in self.models(slug) else "tfidf"
        if method in self.models(slug):
            return self.recommend(slug, liked=[item_id], model=method, k=k, diversify=False)
        domain = self.domain(slug)
        self.validate_ids(domain, [item_id])
        sources = [(slug, item_id)]
        scores = self.content.score(sources, slug)
        return self._rank(domain, scores, sources, {item_id}, k, False, None, False,
                          "Populaire dans ce domaine")

    def _rank(self, domain, scores, sources, excluded, k, diversify, candidates, semantic, fallback):
        ids = domain.model.item_index
        indexes = np.array([i for item, i in ids.items()
                            if item not in excluded and (candidates is None or item in candidates)], dtype=int)
        if indexes.size == 0:
            return []
        normalized = unit_scores(scores)
        rank = np.lexsort((indexes, -domain.model.popularity[indexes], -normalized[indexes]))
        pool = list(indexes[rank[:max(k * 6, 40)]])
        chosen = []
        penalty = float(domain.config.parameters.get("diversity_penalty", 0.1)) if diversify else 0.0
        tags = domain.tags
        for _ in range(min(k, len(pool))):
            def relevance(index):
                overlap = max((len(tags[index] & tags[other]) / max(1, len(tags[index] | tags[other]))
                               for other in chosen), default=0)
                return normalized[index] - penalty * overlap

            best = max(pool, key=relevance)
            pool.remove(best)
            chosen.append(best)
        return [self._explain(domain, index, sources, normalized[index], semantic, fallback) for index in chosen]

    def _explain(self, domain, index, sources, score, semantic, fallback):
        item = domain.catalog[index]
        explanation = fallback
        if sources:
            values = self.content.affinities(sources, (domain.config.slug, item["item_id"]), semantic=semantic)
            best_index = int(np.argmax(values))
            slug, favorite = sources[best_index]
            origin = self.domains[slug].items[favorite]
            raw_tags = {tag.casefold() for tag in item_tags(origin["tags"])}
            common = [tag for tag in item_tags(item["tags"]) if tag.casefold() in raw_tags]
            if common:
                explanation = f'Comme « {origin["titre"]} » · {", ".join(common[:2])}'
            elif values[best_index] > 0.08:
                explanation = f'Des thèmes proches de « {origin["titre"]} »'
            elif score > 0 and fallback != "Aléatoire":
                explanation = "Suggestion selon le classement du modèle"
        return {**self.public_item(item), "score": round(float(score), 5), "explanation": explanation}
