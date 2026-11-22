.DEFAULT_GOAL := all
.NOTPARALLEL: all

.PHONY: all setup advanced demo-data lint test benchmark tune api demo docs build load
all: setup lint test demo-data benchmark docs

setup:
	uv sync --locked --extra serving --extra dev --extra experiments --extra docs

advanced: setup
	uv sync --locked --extra serving --extra dev --extra experiments --extra docs --extra advanced
	uv run --no-sync reco-platform benchmark --semantic --output reports/semantic

demo-data:
	uv run --no-sync reco-platform demo-data

lint:
	uv run --no-sync ruff check .

test:
	uv run --no-sync python -m pytest -q

benchmark:
	uv run --no-sync reco-platform benchmark

tune:
	uv run --no-sync reco-platform tune movies --trials 10

api:
	uv run --no-sync uvicorn api.main:app --host 0.0.0.0 --port 8000 --no-access-log

demo:
	uv run --no-sync streamlit run app/streamlit_app.py

docs:
	uv run --no-sync mkdocs build --strict

build:
	docker build -t prisme:local .

load:
	uv run --locked --extra load locust -f tests/locustfile.py --headless -u 12 -r 4 -t 30s --host http://localhost:8000
