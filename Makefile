.PHONY: setup sim train eval api web check demo clean

setup:
	uv sync --extra dev
	@if [ -f web/package.json ]; then cd web && npm install; fi

sim:
	uv run python -m sim.run

train:
	uv run python -m models.train

eval:
	uv run python -m eval.run

api:
	uv run uvicorn api.main:app --reload --port 8000

web:
	cd web && npm run dev

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy agent models sim features eval api
	uv run pytest -q

demo: sim train eval
	@echo "Run 'make api' and 'make web' in separate terminals."

clean:
	rm -rf data/*.sqlite3 artifacts/*.parquet artifacts/*.json .pytest_cache .mypy_cache .ruff_cache
