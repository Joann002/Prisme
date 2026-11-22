FROM ghcr.io/astral-sh/uv:0.13.9 AS uv

FROM python:3.15-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
RUN sed -i "s|http://deb.debian.org|https://deb.debian.org|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 1000 prisme && useradd --uid 1000 --gid 1000 --create-home prisme
WORKDIR /opt/prisme
RUN chown prisme:prisme /opt/prisme
COPY --chown=prisme:prisme . .
USER prisme
ENV PATH="/opt/prisme/.venv/bin:$PATH" \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1
ARG RECO_PRODUCTION=0
ARG RECO_ADVANCED=0
RUN uv sync --frozen --no-dev --extra serving \
    $(if [ "$RECO_PRODUCTION" = "1" ]; then printf '%s' '--extra production'; fi) \
    $(if [ "$RECO_ADVANCED" = "1" ]; then printf '%s' '--extra advanced'; fi)
EXPOSE 7860 8000
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.address=0.0.0.0", "--server.port=7860"]
