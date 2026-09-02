.PHONY: setup sim train eval sensitivity api web check demo demo-fixture money-chart home-demo compliance-rules ask-why clean

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
	@# data/dobara.sqlite3 is gitignored; tests/test_eval_invariants.py and
	@# tests/test_runner_trace.py need it (via models.ltv.build_life_table /
	@# agent.models.load_model_bundle) and nothing else creates it on a clean checkout.
	@# Deterministic on the default seed, ~13s -- only regenerated if missing.
	@test -f data/dobara.sqlite3 || uv run python -m sim.run
	uv run pytest -q
	uv run python -m scripts.check_ask_why_grounding
	uv run python -m scripts.check_spoken_figures

demo: sim train eval
	@echo "Run 'make api' and 'make web' in separate terminals."

demo-fixture:
	uv run python -m scripts.build_demo_fixture

money-chart:
	uv run python -m scripts.build_money_chart

# The landing page's side-by-side demonstration. Runs two full arms over the seed-301
# population, so it takes about as long as `make money-chart`.
home-demo:
	uv run python -m scripts.build_home_demo

# /architecture's rule list, straight out of agent/compliance.py. Seconds, no trained DB.
compliance-rules:
	uv run python -m scripts.build_compliance_rules

ask-why:
	uv run python -m scripts.generate_ask_why

clean:
	rm -rf data/*.sqlite3 artifacts/*.parquet artifacts/*.json .pytest_cache .mypy_cache .ruff_cache
