.PHONY: setup sim train eval sensitivity api web check demo demo-fixture money-chart ask-why clean

setup:
	uv sync --extra dev
	@if [ -f web/package.json ]; then cd web && npm install; fi

sim:
	uv run python -m sim.run

train:
	uv run python -m models.train

eval:
	uv run python -m eval.run

sensitivity:
	uv run python -m eval.sensitivity

api:
	uv run uvicorn api.main:app --reload --port 8000

web:
	cd web && npm run dev

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy agent models sim features eval api llm scripts
	uv run python -m scripts.check_artifact_freshness
	uv run pytest -q
	uv run python -m scripts.check_ask_why_grounding

demo: sim train eval
	@echo "Run 'make api' and 'make web' in separate terminals."

demo-fixture:
	uv run python -m scripts.build_demo_fixture

money-chart:
	uv run python -m scripts.build_money_chart

ask-why:
	uv run python -m scripts.generate_ask_why

clean:
	rm -rf data/*.sqlite3 artifacts/*.parquet artifacts/*.json .pytest_cache .mypy_cache .ruff_cache
