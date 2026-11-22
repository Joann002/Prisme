from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from api.runtime import LATENCY, Runtime
from api.schemas import (
    Catalog,
    CrossRequest,
    FeedbackRequest,
    Identifier,
    RecommendationList,
    Slug,
    TasteRequest,
)
from reco_platform.service import Recommender, RequestError

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"
LOGGER = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def startup(app):
    app.state.runtime = Runtime(Recommender.load())
    yield


app = FastAPI(title="Prisme API", version="0.1.0", lifespan=startup,
              description="Classements et recommandations explicables sur plusieurs domaines.")


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    if request.method in {"POST", "PUT", "PATCH"}:
        if not runtime(request).limits.allowed(request.client.host if request.client else "unknown"):
            return JSONResponse({"detail": "Trop de requêtes. Réessaie dans une minute."}, 429,
                                headers={"Retry-After": "60"})
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 16384:
            return JSONResponse({"detail": "Corps de requête trop volumineux."}, 413)
        # Bound the payload even when the caller sends it in chunks.
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > 16384:
                return JSONResponse({"detail": "Corps de requête trop volumineux."}, 413)
        request._body = bytes(chunks)
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    route = request.scope.get("route")
    template = getattr(route, "path", "unmatched")
    if template not in {"/assets", "/metrics"}:
        LATENCY.labels(request.method, template, str(response.status_code)).observe(elapsed)
        LOGGER.info("%s %s %s %.1fms", request.method, template, response.status_code, elapsed * 1000)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(RequestError)
async def exception_handler(_request, exc):
    return JSONResponse({"detail": str(exc)}, exc.status)


def runtime(request):
    return request.app.state.runtime


@app.get("/health")
def health(request: Request):
    engine = runtime(request).engine
    return {"status": "ok", "domains": len(engine.domains), "semantic": engine.content.dense is not None}


@app.get("/domains")
def domains(request: Request):
    return runtime(request).engine.metadata()


@app.get("/catalog/{domain}", response_model=Catalog)
def catalog(request: Request, domain: Slug, q: Annotated[str, Query(max_length=100)] = "",
            limit: Annotated[int, Query(ge=1, le=100)] = 30,
            offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0):
    return runtime(request).engine.catalog(domain, q, limit, offset)


@app.get("/recommend", response_model=RecommendationList)
def user_recommend(request: Request, domain: Slug, user_id: Identifier | None = None, model: Slug | None = None,
                   k: Annotated[int, Query(ge=1, le=50)] = 10, diversify: bool = True):
    return runtime(request).user(domain, user_id, model, k, diversify)


@app.post("/recommend/items", response_model=RecommendationList)
def recommend_items(request: Request, body: TasteRequest):
    return runtime(request).taste(body)


@app.get("/similar/{item_id}", response_model=RecommendationList)
def similar(request: Request, item_id: Annotated[str, PathParam(min_length=1, max_length=128)],
            domain: Slug | None = None, k: Annotated[int, Query(ge=1, le=50)] = 10):
    engine = runtime(request).engine
    if domain is None:
        matches = [slug for slug, catalog in engine.domains.items() if item_id in catalog.items]
        if len(matches) > 1:
            raise RequestError("Cet identifiant existe dans plusieurs domaines. Précise le domaine.", 409)
        if not matches:
            raise RequestError("Élément introuvable.", 404)
        domain = matches[0]
    return runtime(request).similar(domain, item_id, k)


@app.post("/cross-recommend", response_model=RecommendationList)
def cross_recommend(request: Request, body: CrossRequest):
    return runtime(request).cross(body)


@app.post("/feedback", status_code=201)
def feedback(request: Request, body: FeedbackRequest):
    return runtime(request).feedback(body)


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/privacy", include_in_schema=False)
def privacy():
    return FileResponse(STATIC / "privacy.html")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    markup = (STATIC / "shell.html").read_text(encoding="utf-8")
    return HTMLResponse(
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="theme-color" content="#151311"><title>Prisme — Découvre ce qui te plaît</title>'
        '<link rel="icon" href="/assets/prisme.svg" type="image/svg+xml">'
        '<link rel="stylesheet" href="/assets/prisme.css"></head><body>'
        f'{markup}<script type="module" src="/assets/http.js"></script></body></html>'
    )


app.mount("/assets", StaticFiles(directory=STATIC), name="assets")
