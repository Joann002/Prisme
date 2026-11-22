from __future__ import annotations

import hashlib
from importlib.util import find_spec

import numpy as np
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
from threadpoolctl import threadpool_limits


def unit_scores(scores: np.ndarray) -> np.ndarray:
    low, high = scores.min(initial=0), scores.max(initial=0)
    return (scores - low) / (high - low) if high > low else np.zeros_like(scores, dtype=float)


class Collaborative:
    def __init__(self, items, events, config, requested: set[str]):
        self.seed = config.seed
        self.item_index = {item: index for index, item in enumerate(items)}
        positives = events[events["feedback"].ge(config.positive)]
        self.users = sorted(positives["user_id"].unique())
        self.user_index = {user: index for index, user in enumerate(self.users)}
        self.histories = {
            user: rows.sort_values("timestamp", kind="stable")["item_id"].tolist()
            for user, rows in positives.groupby("user_id", sort=False)
        }
        self.seen = {
            user: set(items) for user, items in events.groupby("user_id", sort=False)["item_id"]
        }
        self.matrix = sparse.csr_matrix(
            (positives["feedback"].to_numpy(dtype="float32"),
             (positives["user_id"].map(self.user_index).astype(int),
              positives["item_id"].map(self.item_index).astype(int))),
            shape=(len(self.users), len(items)),
        )
        self.counts = np.asarray(self.matrix.getnnz(axis=0)).ravel()
        self.popularity = unit_scores(np.log1p(self.counts))
        self.knn = normalize(self.matrix.T.tocsr(), copy=True) if "knn" in requested else None
        self.svd = None
        self.als = None
        parameters = config.parameters
        limit = min(self.matrix.shape)
        # Fit once per catalog. With fewer than two rows or columns, popularity remains available.
        if limit >= 2 and requested & {"svd", "als"}:
            factors = max(1, min(int(parameters.get("factors", 12)), limit - 1))
            with threadpool_limits(limits=1):
                if "svd" in requested:
                    decomposition = TruncatedSVD(n_components=factors, random_state=self.seed, n_iter=8)
                    self.svd = (decomposition.fit_transform(self.matrix), decomposition.components_.T)
                if "als" in requested and find_spec("implicit") is not None:
                    from implicit.als import AlternatingLeastSquares

                    als = AlternatingLeastSquares(
                        factors=factors, regularization=float(parameters.get("als_regularization", 0.15)),
                        iterations=int(parameters.get("als_iterations", 12)), use_gpu=False,
                        num_threads=1, random_state=self.seed,
                    )
                    weighted = self.matrix.copy()
                    weighted.data = (1 + float(parameters.get("als_alpha", 12)) *
                                     weighted.data / weighted.data.max())
                    als.fit(weighted, show_progress=False)
                    self.als = (als.user_factors, als.item_factors)

    def available(self, model):
        return {"knn": self.knn, "svd": self.svd, "als": self.als}.get(model, True) is not None

    def score(self, model: str, likes: list[str], user: str | None) -> np.ndarray:
        known = [self.item_index[item] for item in likes if self.counts[self.item_index[item]]]
        if model == "random":
            key = "|".join(sorted(likes)) + (user or "")
            seed = int.from_bytes(hashlib.blake2s(key.encode(), digest_size=4).digest(), "big")
            return np.random.default_rng(self.seed + seed).random(len(self.counts))
        if model == "popular":
            return self.popularity.copy()
        if model == "knn" and self.knn is not None and known:
            profile = sparse.csr_matrix(self.knn[known].mean(axis=0))
            return (self.knn @ profile.T).toarray().ravel()
        factors = self.svd if model == "svd" else self.als if model == "als" else None
        if factors is not None:
            users, items = factors
            if user in self.user_index:
                return items @ users[self.user_index[user]]
            if known:
                profile = normalize(items[known].mean(axis=0, keepdims=True))[0]
                return normalize(items) @ profile
        return np.zeros(len(self.counts))

    def transfer_from(self, source, seeds):
        """Propagate through aligned users and two sparse interaction matrices."""
        aligned = sorted(self.user_index.keys() & source.user_index.keys())
        if not aligned:
            return np.zeros(len(self.counts))
        seed_indices = [source.item_index[item] for item in seeds]
        source_indices = [source.user_index[user] for user in aligned]
        target_indices = [self.user_index[user] for user in aligned]
        affinity = np.asarray(source.matrix[source_indices][:, seed_indices].getnnz(axis=1)).ravel()
        target = self.matrix[target_indices]
        totals = np.asarray(target.getnnz(axis=0)).ravel()
        hits = np.asarray(target.sign().T @ affinity).ravel()
        return hits / np.maximum(np.sqrt(totals), 1)
