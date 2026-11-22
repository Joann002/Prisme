"""Prépare ou publie une révision Git de Prisme vers un Space Docker existant."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SPACE_FILES = (
    ".dockerignore", ".github/workflows/ci.yml", ".streamlit", "Dockerfile", "LICENSE",
    "README.md", "api", "app", "data/demo", "docs", "notebooks", "pyproject.toml",
    "reports", "src", "uv.lock",
)


def stage(folder: Path, revision: str) -> str:
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"],
        cwd=ROOT, text=True,
    ).strip()
    archive = folder.parent / "prisme.tar"
    with archive.open("wb") as output:
        subprocess.run(
            ["git", "archive", "--format=tar", commit, "--", *SPACE_FILES],
            cwd=ROOT, stdout=output, check=True,
        )
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        if any(not (member.isfile() or member.isdir()) for member in members):
            raise ValueError("L’archive du Space contient un lien ou un fichier spécial.")
        bundle.extractall(folder, members=members, filter="data")
    return commit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--space", default=os.getenv("HF_SPACE_ID"))
    parser.add_argument("--dry-run", action="store_true", help="Prépare l’archive sans accès réseau.")
    args = parser.parse_args()
    token = os.getenv("HF_TOKEN")
    if not args.dry_run:
        if not args.space or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.space):
            parser.error("Indique le Space existant comme COMPTE/NOM.")
        if not token:
            parser.error("Configure HF_TOKEN avant la publication.")
    with TemporaryDirectory() as directory:
        folder = Path(directory) / "space"
        commit = stage(folder, args.revision)
        if args.dry_run:
            files = [path.relative_to(folder) for path in folder.rglob("*") if path.is_file()]
            print(f"{commit[:12]} · {len(files)} fichiers prêts pour Hugging Face Spaces")
            for path in sorted(files):
                print(path)
            return

        from huggingface_hub import HfApi

        hub = HfApi(token=token)
        space = hub.space_info(args.space, revision="main")
        if space.sdk != "docker":
            parser.error("Le Space doit utiliser le SDK Docker.")
        result = hub.upload_folder(
            folder_path=folder, repo_id=args.space, repo_type="space", revision="main",
            parent_commit=space.sha, commit_message=f"Deploy Prisme {commit[:12]}",
        )
        print(f"Révision envoyée sur {result.commit_url}")
        print(f"Vérifie la construction et le démarrage sur https://huggingface.co/spaces/{args.space}")


if __name__ == "__main__":
    main()
