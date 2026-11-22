from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from itertools import permutations
from pathlib import Path

import pandas as pd

from reco_platform.evaluation.metrics import summary
from reco_platform.evaluation.split import leave_last_out
from reco_platform.features.content import item_tags
from reco_platform.service import Recommender

HOLDOUT_K = 5


def summarize(model, slug, examples, scenario, name, k):
    domain = model.domain(slug)
    popularity = dict(zip(domain.model.item_index, domain.model.counts.tolist()))
    tags = {item_id: set(item_tags(item["tags"])) for item_id, item in domain.items.items()}
    result = summary(examples, k, domain.items, tags, popularity)
    return {"scenario": scenario, "domain": slug, "model": name,
            "dataset": "demo" if domain.dataset.demo else "import", **result} if result else None


def requirements(configs, datasets):
    train, test = {}, {}
    for slug, dataset in datasets.items():
        if not dataset.temporal:
            continue
        fit, held = leave_last_out(dataset.interactions, configs[slug].positive)
        train[slug] = replace(dataset, interactions=fit)
        test[slug] = held
    return train, test


def evaluate_domain(engine, slug, held, model, k, scenario="warm", *, source=None, diversify=True):
    examples = []
    for user, rows in held.groupby("user_id"):
        relevant = set(rows["item_id"])
        if scenario == "new_user_0":
            picks = engine.recommend(slug, model=model, k=k, diversify=diversify)
        elif scenario == "new_user_3":
            previous = source[source["user_id"].eq(user)]
            positives = previous.loc[previous["feedback"].ge(engine.domain(slug).config.positive)]
            likes = positives.sort_values("timestamp", kind="stable")["item_id"].tail(3).tolist()
            if len(likes) < 3:
                continue
            picks = engine.recommend(slug, liked=likes, model=model, k=k, diversify=diversify)
        else:
            picks = engine.recommend(slug, user=user, model=model, k=k, diversify=diversify)
        examples.append(([pick["item_id"] for pick in picks], relevant))
    return summarize(engine, slug, examples, scenario, model, k)


def cold_users(configs, datasets, semantic_model, k):
    training, previously_liked, held_out = {}, {}, {}
    for slug, dataset in datasets.items():
        users = sorted(dataset.interactions["user_id"].unique())
        strangers = set(users[::5])
        events = dataset.interactions
        onboarding, held = leave_last_out(events[events["user_id"].isin(strangers)], configs[slug].positive)
        training[slug] = replace(dataset, interactions=events[~events["user_id"].isin(strangers)])
        previously_liked[slug] = onboarding
        held_out[slug] = held
    engine = Recommender(configs, training, semantic_model=semantic_model, only={"hybrid", "advanced"})
    rows = []
    for slug in configs:
        for scenario in ("new_user_0", "new_user_3"):
            names = (["popular"] if scenario == "new_user_0"
                     else ["popular", "tfidf", "knn", "svd", "als", "hybrid", "semantic", "advanced"])
            for model in (name for name in names if name in engine.models(slug)):
                rows.append(evaluate_domain(engine, slug, held_out[slug], model, k, scenario,
                                            source=previously_liked[slug]))
    return rows


def cold_items(configs, datasets, semantic_model, k):
    rows = []
    for slug, dataset in datasets.items():
        events = dataset.interactions
        first = events.groupby("item_id")["timestamp"].min().sort_values()
        if len(first) < 4:
            continue
        cutoff = first.iloc[max(1, int(len(first) * 0.8))]
        new = set(first[first.ge(cutoff)].index)
        training = events[events["timestamp"].lt(cutoff)]
        positives = events[events["item_id"].isin(new) & events["feedback"].ge(configs[slug].positive)]
        engine = Recommender({slug: configs[slug]}, {slug: replace(dataset, interactions=training)},
                             semantic_model=semantic_model, only={"popular", "tfidf", "semantic"})
        for model in (name for name in ("popular", "tfidf", "semantic") if name in engine.models(slug)):
            rows.append(evaluate_domain(engine, slug, positives, model, k, "new_item"))
    return rows


def cross_cases(engine, k, relations=None):
    rows = []
    for source, target in permutations(engine.domains, 2):
        origin, destination = engine.domain(source), engine.domain(target)
        explicit = relations is not None
        if not explicit and not (origin.dataset.demo and destination.dataset.demo):
            continue
        labels = defaultdict(set)
        if explicit:
            subset = relations.loc[
                relations["source_domain"].eq(source) & relations["target_domain"].eq(target)
            ]
            for row in subset.itertuples():
                if row.source_id not in origin.items or row.target_id not in destination.items:
                    raise ValueError("Lien cross-domain vers un item absent du catalogue.")
                labels[row.source_id].add(row.target_id)
        for label in (("external",) if explicit else ("entity", "theme")):
            by_label = defaultdict(set)
            if not explicit:
                for item in destination.catalog:
                    if item[label]:
                        by_label[item[label]].add(item["item_id"])
            for method in ("tfidf", "text", "hybrid"):
                if method == "text" and engine.content.dense is None:
                    continue
                if method == "hybrid" and not engine.has_shared_users(origin, destination):
                    continue
                examples = []
                for item in origin.catalog:
                    relevant = labels[item["item_id"]] if explicit else by_label[item[label]]
                    if relevant:
                        picks = engine.cross_recommend(source, target, [item["item_id"]], method=method,
                                                       k=k, diversify=False)
                        examples.append(([pick["item_id"] for pick in picks], relevant))
                result = summarize(engine, target, examples, f"cross_{label}", method, k)
                if result:
                    rows.append({**result, "source": source,
                                 "signal": "semantic" if method != "tfidf" and
                                 engine.content.dense is not None else "tfidf"})
    return rows


def benchmark(configs, datasets, k=HOLDOUT_K, semantic_model=None, relations=None, shared_users=False):
    training, held_out = requirements(configs, datasets)
    if not training:
        raise ValueError("Aucun domaine ne contient de données horodatées.")
    temporal_configs = {slug: configs[slug] for slug in training}
    engine = Recommender(temporal_configs, training, semantic_model=semantic_model, shared_users=shared_users)
    rows = []
    for slug in training:
        rows.extend(evaluate_domain(engine, slug, held_out[slug], name, k)
                    for name in engine.models(slug))
    rows.extend(cold_users(temporal_configs, {slug: datasets[slug] for slug in training}, semantic_model, k))
    rows.extend(cold_items(temporal_configs, {slug: datasets[slug] for slug in training}, semantic_model, k))
    no_tags = Recommender(temporal_configs, training, semantic_model=semantic_model, include_tags=False,
                          only={"tfidf", "semantic", "hybrid", "advanced"})
    for slug in training:
        for name in (model for model in ("tfidf", "hybrid", "semantic", "advanced")
                     if model in no_tags.models(slug)):
            rows.append(evaluate_domain(no_tags, slug, held_out[slug], name, k, "without_tags"))
        if "hybrid" in engine.models(slug):
            rows.append(evaluate_domain(engine, slug, held_out[slug], "hybrid", k,
                                        "without_reranking", diversify=False))
    rows.extend(cross_cases(engine, k, relations))
    frame = pd.DataFrame([row for row in rows if row is not None])
    if frame.empty:
        raise ValueError("Aucun cas évaluable après le découpage chronologique.")
    return frame


def tune(config, dataset, trials, tracking_uri=None):
    import optuna

    if not dataset.temporal:
        raise ValueError("Le tuning exige des interactions horodatées.")
    outer, _ = leave_last_out(dataset.interactions, config.positive)
    inner, held = leave_last_out(outer, config.positive)
    if held.empty:
        raise ValueError("Historique insuffisant pour la validation chronologique imbriquée.")
    tuning = config.tuning
    mlflow = None
    if tracking_uri:
        import mlflow
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("Prisme • validation temporelle")

    def objective(trial):
        parameters = dict(config.parameters)
        if "factors" in tuning:
            parameters["factors"] = trial.suggest_categorical("factors", tuning["factors"])
        if "hybrid_weight" in tuning:
            parameters["hybrid_weight"] = trial.suggest_float("hybrid_weight", *tuning["hybrid_weight"])
        if "als_regularization" in tuning:
            parameters["als_regularization"] = trial.suggest_float(
                "als_regularization", *tuning["als_regularization"], log=True)
        candidate = replace(config, parameters=parameters)
        engine = Recommender({config.slug: candidate}, {config.slug: replace(dataset, interactions=inner)},
                             only={"hybrid"})
        row = evaluate_domain(engine, config.slug, held, "hybrid", HOLDOUT_K)
        if mlflow:
            with mlflow.start_run(run_name=f"{config.slug}-{trial.number}"):
                mlflow.log_params({"domain": config.slug, "seed": config.seed, **parameters})
                mlflow.log_metrics({key: value for key, value in row.items() if isinstance(value, (int, float))})
        return row["ndcg"]

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=config.seed))
    study.optimize(objective, n_trials=trials)
    return {"domain": config.slug, "best_ndcg": study.best_value, "parameters": study.best_params}


def report_curves(frame, path: Path):
    warm = frame[frame["scenario"].eq("warm")]
    domains = list(warm["domain"].unique())
    models = list(warm["model"].unique())
    colors = ["#7257aa", "#e49138", "#427b9b", "#288369", "#c14c61"]
    width, height = 890, 350
    if not models:
        return
    from html import escape
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
             "<title>NDCG par modèle et domaine</title>",
             '<rect width="100%" height="100%" fill="#faf8f4"/>',
             '<g font-family="sans-serif" font-size="13" fill="#241f21">',
             '<text x="36" y="28" font-size="18" font-weight="bold">NDCG par modèle et domaine</text>']
    for tick in range(6):
        y = 268 - tick * 41
        parts += [f'<path d="M58 {y} H850" stroke="#dfdad4"/>',
                  f'<text x="22" y="{y + 4}">{tick / 5:.1f}</text>']
    x = {model: 70 + index * 755 / max(1, len(models) - 1) for index, model in enumerate(models)}
    for model in models:
        parts.append(f'<text x="{x[model]}" y="293" text-anchor="middle">{escape(model)}</text>')
    for i, slug in enumerate(domains):
        color = colors[i % len(colors)]
        coordinates = [(x[row.model], 268 - row.ndcg * 205)
                       for row in warm.loc[warm["domain"].eq(slug)].itertuples()]
        points = " ".join(f"{horizontal:.1f},{vertical:.1f}" for horizontal, vertical in coordinates)
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        for horizontal, vertical in coordinates:
            parts.append(f'<circle cx="{horizontal:.1f}" cy="{vertical:.1f}" r="4" fill="{color}"/>')
        parts.append(f'<text x="{65 + i * 113}" y="323" fill="{color}">{escape(slug)}</text>')
    path.write_text("".join(parts + ["</g></svg>"]), encoding="utf-8")
