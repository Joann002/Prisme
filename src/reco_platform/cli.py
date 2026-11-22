from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from .config import load_configs
from .data import data_root, demo_dataset, read_dataset, write_dataset
from .domains.base import adapter_for
from .evaluation.run import benchmark, report_curves, tune
from .service import SEMANTIC_MODEL, Recommender


def arguments():
    parser = argparse.ArgumentParser(prog="reco-platform")
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser("demo-data", help="Versionner la démo en Parquet")
    demo.add_argument("--output", type=Path, default=data_root())
    ingest = commands.add_parser("ingest", help="Importer les données sources d’un domaine")
    ingest.add_argument("domain")
    ingest.add_argument("source", type=Path)
    ingest.add_argument("--output", type=Path, default=data_root())
    bench = commands.add_parser("benchmark", help="Évaluer les modèles sur les domaines horodatés")
    bench.add_argument("--data", type=Path, default=data_root())
    bench.add_argument("--output", type=Path, default=Path("reports"))
    bench.add_argument("--k", type=int, choices=range(1, 21), default=5, metavar="1-20")
    bench.add_argument("--semantic", nargs="?", const=SEMANTIC_MODEL, metavar="MODELE")
    bench.add_argument("--relations", type=Path)
    bench.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI"))
    search = commands.add_parser("tune", help="Ajuster un modèle par validation temporelle imbriquée")
    search.add_argument("domain")
    search.add_argument("--data", type=Path, default=data_root())
    search.add_argument("--trials", type=int, default=10)
    search.add_argument("--tracking-uri", default=os.getenv("MLFLOW_TRACKING_URI"))
    warm = commands.add_parser("precompute", help="Précalculer les recommandations populaires")
    warm.add_argument("--output", type=Path, default=Path("data/processed/warm.json"))
    export = commands.add_parser("export-content", help="Exporter les vecteurs pour reconstruire l’index FAISS")
    export.add_argument("--data", type=Path, default=data_root())
    export.add_argument("--output", type=Path, default=Path("data/processed/vectors.npz"))
    export.add_argument("--semantic", default=os.getenv("RECO_SEMANTIC_MODEL") or SEMANTIC_MODEL)
    return parser


def main():
    parser = arguments()
    args = parser.parse_args()
    configs = load_configs()
    slug = getattr(args, "domain", None)
    if slug and slug not in configs:
        parser.error(f"Domaine inconnu : {slug}. Choix possibles : {', '.join(configs)}")
    if args.command == "demo-data":
        for slug, config in configs.items():
            try:
                dataset = demo_dataset(config)
            except KeyError:
                continue
            target = args.output / slug
            if (target / "manifest.json").exists() and not read_dataset(config, args.output).demo:
                print(f"{slug} : import externe conservé")
                continue
            manifest = write_dataset(dataset, target, "Démonstration synthétique")
            print(slug, {name: table["rows"] for name, table in manifest["files"].items()})
    elif args.command == "ingest":
        dataset = adapter_for(configs[slug]).load(args.source, filter_interactions=False)
        if dataset.items.empty or dataset.interactions.empty:
            parser.error("Import vide après nettoyage. Vérifiez le format, les identifiants et les dates.")
        manifest = write_dataset(dataset, args.output / slug, configs[slug].source["label"])
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    elif args.command == "benchmark":
        datasets = {slug: read_dataset(config, args.data) for slug, config in configs.items()}
        for slug, dataset in datasets.items():
            if not dataset.temporal:
                print(f"{slug} : exclu du benchmark temporel (dates absentes).")
        relations = pd.read_csv(args.relations, dtype=str) if args.relations else None
        frame = benchmark(configs, datasets, k=args.k, semantic_model=args.semantic, relations=relations,
                          shared_users=os.getenv("RECO_SHARED_USERS") == "1")
        args.output.mkdir(parents=True, exist_ok=True)
        results = args.output / "benchmark.csv"
        frame.to_csv(results, index=False, float_format="%.6f")
        report_curves(frame, args.output / "ndcg.svg")
        if args.tracking_uri:
            log_results(args.tracking_uri, frame, args, results)
        print(frame.query('scenario == "warm"').pivot(index="model", columns="domain", values="ndcg").round(3))
        print(f"Résultats écrits dans {results}")
    elif args.command == "tune":
        if args.trials < 1:
            parser.error("Le nombre d’essais doit être positif.")
        result = tune(configs[slug], read_dataset(configs[slug], args.data), args.trials, args.tracking_uri)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "precompute":
        engine = Recommender.load()
        results = {slug: engine.recommend(slug, model="popular") for slug in engine.domains
                   if "popular" in engine.models(slug)}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    elif args.command == "export-content":
        datasets = {slug: read_dataset(config, args.data) for slug, config in configs.items()}
        engine = Recommender(configs, datasets, semantic_model=args.semantic, only=set())
        engine.content.export_vectors(args.output)
        print(f"Vecteurs exportés dans {args.output}")


def log_results(uri, frame, args, results):
    import mlflow
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("Prisme • benchmark")
    with mlflow.start_run(run_name="benchmark"):
        mlflow.log_artifact(str(results), artifact_path="rapports")
        curves = results.with_name("ndcg.svg")
        if curves.exists():
            mlflow.log_artifact(str(curves), artifact_path="rapports")
        for row in frame.to_dict("records"):
            with mlflow.start_run(run_name=f'{row["scenario"]}/{row["domain"]}/{row["model"]}', nested=True):
                mlflow.log_params({key: row[key] for key in ("scenario", "domain", "model", "dataset")})
                mlflow.log_param("semantic_model", args.semantic or "disabled")
                metrics = {key: row[key] for key in ("k", "cases", "precision", "recall", "ndcg", "map",
                                                   "coverage", "diversity", "novelty_bits", "head_share")}
                mlflow.log_metrics(metrics)


if __name__ == "__main__":
    main()
