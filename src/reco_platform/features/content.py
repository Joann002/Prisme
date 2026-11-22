from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize


def item_tags(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(tag.strip() for tag in re.split(r"[,|]", value) if tag.strip()))


def text_of(item: dict, include_tags: bool) -> str:
    tags = " ".join(item_tags(item["tags"])) if include_tags else ""
    return f'{item["titre"]}. {item["description"]} {tags} {tags}'.strip()


class ContentSpace:
    def __init__(self, catalogs: dict, model_name: str | None = None, include_tags: bool = True,
                 index_path: Path | None = None):
        self.lookup = {}
        docs = []
        self.slices = {}
        for domain, catalog in catalogs.items():
            start = len(docs)
            for item in catalog:
                self.lookup[(domain, item["item_id"])] = len(docs)
                docs.append(text_of(item, include_tags))
            self.slices[domain] = slice(start, len(docs))
        self.fingerprint = hashlib.sha256(
            json.dumps([list(self.lookup), docs], ensure_ascii=False).encode()
        ).hexdigest()
        self.tfidf = TfidfVectorizer(
            strip_accents="unicode", ngram_range=(1, 2), sublinear_tf=True, max_features=120_000
        )
        try:
            self.sparse = self.tfidf.fit_transform(docs).tocsr()
        except ValueError as error:
            if "empty vocabulary" not in str(error):
                raise
            self.sparse = sparse.csr_matrix((len(docs), 1), dtype=float)
        self.dense = None
        self.indexes = {}
        if index_path:
            with np.load(index_path, allow_pickle=False) as exported:
                if exported["fingerprint"].item() != self.fingerprint:
                    raise ValueError("L’index sémantique ne correspond pas au catalogue.")
                self._set_vectors(exported["vectors"])
        elif model_name:
            self._fit_semantic(docs, model_name)

    def _fit_semantic(self, docs, model_name):
        from sentence_transformers import SentenceTransformer

        encoder = SentenceTransformer(model_name, device="cpu", trust_remote_code=False)
        self._set_vectors(encoder.encode(docs, batch_size=32, normalize_embeddings=True, show_progress_bar=False))

    def _set_vectors(self, vectors):
        import faiss

        if (vectors.ndim != 2 or len(vectors) != len(self.lookup)
                or vectors.shape[1] < 1 or not np.isfinite(vectors).all()):
            raise ValueError("Dimensions ou valeurs invalides dans l’index sémantique.")
        self.dense = np.ascontiguousarray(vectors, dtype="float32")
        for domain, indices in self.slices.items():
            index = faiss.IndexFlatIP(self.dense.shape[1])
            index.add(self.dense[indices])
            self.indexes[domain] = index

    def export_vectors(self, output: Path):
        if self.dense is None:
            raise ValueError("Chargez un modèle sémantique pour exporter ses vecteurs.")
        output.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=output.parent, delete=False) as file:
            temporary = Path(file.name)
        try:
            with temporary.open("wb") as file:
                np.savez_compressed(file, fingerprint=self.fingerprint, vectors=self.dense)
            temporary.replace(output)
        finally:
            temporary.unlink(missing_ok=True)

    def score(self, sources: list[tuple[str, str]], domain: str, *, semantic=False) -> np.ndarray:
        indices = self.slices[domain]
        size = indices.stop - indices.start
        known = [self.lookup[key] for key in sources if key in self.lookup]
        if not known:
            return np.zeros(size)
        if semantic and self.dense is not None:
            query = np.ascontiguousarray(normalize(self.dense[known].mean(axis=0, keepdims=True)))
            distances, positions = self.indexes[domain].search(query, size)
            scores = np.zeros(size)
            scores[positions[0]] = distances[0]
            return np.maximum(scores, 0)
        profile = normalize(sparse.csr_matrix(self.sparse[known].mean(axis=0)))
        return (self.sparse[indices] @ profile.T).toarray().ravel()

    def affinities(self, sources: list[tuple[str, str]], target: tuple[str, str], *, semantic=False):
        reference = self.lookup[target]
        indices = [self.lookup[key] for key in sources]
        if semantic and self.dense is not None:
            return self.dense[indices] @ self.dense[reference]
        return (self.sparse[indices] @ self.sparse[reference].T).toarray().ravel()
