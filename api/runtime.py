from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections import Counter, OrderedDict
from datetime import date, timedelta
from itertools import combinations
from threading import RLock

from prometheus_client import Counter as MetricCounter
from prometheus_client import Histogram

from reco_platform.evaluation.metrics import distance
from reco_platform.service import RequestError

from .schemas import CrossRequest, FeedbackRequest, TasteRequest

LOGGER = logging.getLogger("prisme")
LATENCY = Histogram("prisme_http_seconds", "Latence de l’API", ["method", "route", "status"])
FEEDBACK = MetricCounter("prisme_feedback", "Votes agrégés", ["domain", "vote"])
SERVED = MetricCounter("prisme_recommendations", "Éléments renvoyés", ["domain", "model", "bucket"])
DIVERSITY = Histogram("prisme_list_diversity", "Distance de Jaccard moyenne par liste",
                      ["domain", "model"], buckets=(0, .2, .4, .6, .8, 1))


class Cache:
    def __init__(self, size=512, ttl=300):
        self.size = size
        self.ttl = ttl
        self.lock = RLock()
        self.local = OrderedDict()
        self.namespace = os.getenv("RECO_CACHE_VERSION")
        redis_url = os.getenv("RECO_REDIS_URL")
        self.redis = None
        self.redis_error = OSError
        if redis_url:
            from redis import Redis
            from redis.exceptions import RedisError

            self.redis_error = RedisError
            if not self.namespace:
                raise ValueError("RECO_CACHE_VERSION est obligatoire avec Redis.")
            self.redis = Redis.from_url(redis_url, socket_timeout=0.5, decode_responses=True)

    def get_or_set(self, payload, compute):
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        now = time.monotonic()
        with self.lock:
            previous = self.local.get(key)
            if previous and previous[0] >= now:
                self.local.move_to_end(key)
                return previous[1]
        if self.redis:
            try:
                remote = self.redis.get(f"prisme:{self.namespace}:{key}")
                if remote is not None:
                    return self.remember(key, json.loads(remote))
            except self.redis_error:
                LOGGER.warning("Cache Redis indisponible")
        value = compute()
        if self.redis:
            try:
                self.redis.setex(f"prisme:{self.namespace}:{key}", self.ttl, json.dumps(value))
            except self.redis_error:
                LOGGER.warning("Cache Redis indisponible")
        return self.remember(key, value)

    def remember(self, key, value):
        with self.lock:
            self.local[key] = (time.monotonic() + self.ttl, value)
            self.local.move_to_end(key)
            while len(self.local) > self.size:
                self.local.popitem(last=False)
        return value


class FeedbackStore:
    def __init__(self):
        self.dsn = os.getenv("RECO_DATABASE_URL")
        self.totals = Counter()
        self.lock = RLock()
        if self.dsn:
            with self.connect() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS prisme_feedback (
                        day DATE NOT NULL,
                        domain TEXT NOT NULL,
                        item_id TEXT NOT NULL,
                        vote TEXT NOT NULL CHECK (vote IN ('up', 'down')),
                        total BIGINT NOT NULL DEFAULT 0,
                        PRIMARY KEY(day, domain, item_id, vote)
                    )
                """)

    def connect(self):
        import psycopg

        return psycopg.connect(self.dsn, connect_timeout=3)

    def record(self, domain, item_id, vote):
        today = date.today()
        if self.dsn:
            with self.connect() as conn:
                conn.execute("""
                    INSERT INTO prisme_feedback(day, domain, item_id, vote, total)
                    VALUES (%s, %s, %s, %s, 1)
                    ON CONFLICT (day, domain, item_id, vote)
                    DO UPDATE SET total = prisme_feedback.total + 1
                """, (today, domain, item_id, vote))
        else:
            with self.lock:
                self.totals[(today, domain, item_id, vote)] += 1
                if len(self.totals) > 5000:
                    limit = today - timedelta(days=7)
                    self.totals = Counter({key: total for key, total in self.totals.items() if key[0] >= limit})
                    if len(self.totals) > 5000:
                        self.totals.pop(next(iter(self.totals)))


class Limits:
    def __init__(self):
        self.maximum = max(1, int(os.getenv("RECO_RATE_LIMIT", "120")))
        self.lock = RLock()
        self.peers = OrderedDict()
        self.salt = os.urandom(16)

    def allowed(self, peer):
        key = hashlib.blake2b(peer.encode(), key=self.salt, digest_size=16).digest()
        now = int(time.monotonic() // 60)
        with self.lock:
            window, count = self.peers.get(key, (now, 0))
            count = count + 1 if window == now else 1
            self.peers[key] = (now, count)
            self.peers.move_to_end(key)
            while len(self.peers) > 8192:
                self.peers.popitem(last=False)
        return count <= self.maximum


class Runtime:
    def __init__(self, engine):
        self.engine = engine
        self.cache = Cache()
        self.feedback_store = FeedbackStore()
        self.limits = Limits()
        self.top = {}
        for slug, domain in engine.domains.items():
            count = max(1, round(0.2 * len(domain.items)))
            self.top[slug] = {item for item, _ in sorted(
                domain.model.item_index.items(), key=lambda pair: (-domain.model.counts[pair[1]], pair[0])
            )[:count]}
            if "popular" not in engine.models(slug):
                continue
            for k in domain.config.parameters.get("warm_popular", []):
                self.cached_taste(TasteRequest(domain=slug, model="popular", k=k))

    def cached_taste(self, body):
        model = body.model or self.engine.default_model(body.domain)
        payload = {**body.model_dump(), "model": model}
        return model, self.cache.get_or_set(
            ["taste", payload],
            lambda: self.engine.recommend(body.domain, liked=body.liked, model=model, k=body.k,
                                          diversify=body.diversify),
        )

    def taste(self, body: TasteRequest):
        model, items = self.cached_taste(body)
        return self.wrap(body.domain, model, items)

    def user(self, slug, user, model, k, diversify):
        model = model or self.engine.default_model(slug)
        if user is None:
            return self.taste(TasteRequest(domain=slug, model=model, k=k, diversify=diversify))
        items = self.cache.get_or_set(
            ["user", slug, user, model, k, diversify],
            lambda: self.engine.recommend(slug, user=user, model=model, k=k, diversify=diversify),
        )
        return self.wrap(slug, model, items)

    def cross(self, body: CrossRequest):
        items = self.cache.get_or_set(
            ["cross", body.model_dump()],
            lambda: self.engine.cross_recommend(body.source_domain, body.target_domain, body.liked,
                                                method=body.method, k=body.k, diversify=body.diversify),
        )
        return self.wrap(body.target_domain, f"cross_{body.method}", items)

    def similar(self, slug, item, k):
        model = "semantic" if "semantic" in self.engine.models(slug) else "tfidf"
        items = self.cache.get_or_set(["similar", slug, item, k], lambda: self.engine.similar(slug, item, k=k))
        return self.wrap(slug, model, items)

    def feedback(self, body: FeedbackRequest):
        self.engine.validate_ids(self.engine.domain(body.domain), [body.item_id])
        self.feedback_store.record(body.domain, body.item_id, body.vote)
        FEEDBACK.labels(body.domain, body.vote).inc()
        return {"ok": True}

    def wrap(self, slug, model, items):
        head = sum(item["item_id"] in self.top[slug] for item in items)
        SERVED.labels(slug, model, "top_20pct").inc(head)
        SERVED.labels(slug, model, "tail").inc(len(items) - head)
        tags = [set(item["tags"]) for item in items]
        pairs = [distance(a, b) for a, b in combinations(tags, 2)]
        if pairs:
            DIVERSITY.labels(slug, model).observe(sum(pairs) / len(pairs))
        return {"domain": slug, "model": model, "recommendations": items}

    def operation(self, action, payload):
        if not isinstance(payload, dict):
            raise RequestError("Paramètres invalides.", 422)
        if action == "catalog":
            slug, query = payload.get("domain"), payload.get("q", "")
            limit, offset = payload.get("limit", 6), payload.get("offset", 0)
            if (not isinstance(slug, str) or not isinstance(query, str) or len(query) > 100
                    or type(limit) is not int or not 1 <= limit <= 100
                    or type(offset) is not int or not 0 <= offset <= 1_000_000):
                raise RequestError("Filtre de catalogue invalide.", 422)
            return self.engine.catalog(slug, query, limit, offset)
        if action == "taste":
            return self.taste(TasteRequest.model_validate(payload))
        if action == "cross":
            return self.cross(CrossRequest.model_validate(payload))
        if action == "feedback":
            return self.feedback(FeedbackRequest.model_validate(payload))
        raise RequestError("Action indéfinie.", 404)
