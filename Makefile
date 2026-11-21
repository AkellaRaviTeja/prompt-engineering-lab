# Prompt Engineering Lab. Run `make help` for the list.
SHELL := /bin/bash
.DEFAULT_GOAL := help
PROMPTFOO := npx --yes promptfoo@0.124.1
MODELS := qwen3:1.7b qwen3:0.6b qwen3:4b
OLLAMA_HOST ?= http://localhost:11434
# A native install often sets OLLAMA_HOST without a scheme (127.0.0.1:11434); curl needs one.
OLLAMA_URL := $(if $(findstring ://,$(OLLAMA_HOST)),$(OLLAMA_HOST),http://$(OLLAMA_HOST))
# Start the container only when nothing answers at OLLAMA_URL yet. A native Ollama
# (or the container from an earlier run) already holds port 11434, and a second bind fails.
define start_ollama
	@if curl -fsS -m 3 $(OLLAMA_URL)/api/version >/dev/null 2>&1; then \
	   echo "up: Ollama already answers at $(OLLAMA_URL), using it and not starting Docker"; \
	 elif ! command -v docker >/dev/null 2>&1; then \
	   echo "up: nothing answers at $(OLLAMA_URL) and Docker is not installed."; \
	   echo "    Install Docker, or start a native Ollama with \`ollama serve\`, then rerun."; exit 1; \
	 else docker compose $(1) up -d; fi
endef
# Use the Docker container when it is running, otherwise a native `ollama` binary.
# Recursive `=` so the check runs when a recipe uses it, after `up` has started the container.
OLLAMA = $(shell docker ps --format '{{.Names}}' 2>/dev/null | grep -qx pel-ollama && echo "docker exec pel-ollama ollama" || echo ollama)

# The tier a lesson runs on: local (Ollama, the default) or hosted (a provider's API).
TIER ?= local
# RECORD=1 saves a hosted run to recordings/hosted/; REPLAY=1 answers from it with no key.
LESSON_ENV = LANTERN_TIER=$(TIER) $(if $(RECORD),LANTERN_RECORD=1) $(if $(REPLAY),LANTERN_REPLAY=1)
# promptfoo runs the Python provider and judge with this interpreter (it needs lantern).
export PROMPTFOO_PYTHON := $(CURDIR)/.venv/bin/python

.PHONY: help setup install up up-gpu down models doctor lesson lessons shots charts diagrams \
        eval eval-view shots-promptfoo check release-check hosted-check lint test prose structure \
        smoke clean quiz exercise exercise-reset hint solution challenge progress notebooks \
        notebooks-check notebook judge-calibrate capstone capstone-solution capstone-live

help: ## Show this help
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: install up models doctor ## One command: install, start Ollama, pull models, check
	@echo "Ready. Start with: make lesson N=01"

install: ## Install Python dependencies with uv
	uv sync

up: ## Start Ollama in Docker (CPU), unless one is already running
	$(call start_ollama,)

up-gpu: ## Start Ollama in Docker with an NVIDIA GPU, unless one is already running
	$(call start_ollama,-f docker-compose.yml -f docker-compose.gpu.yml)

down: ## Stop the Ollama container (models are kept in a volume)
	docker compose down

models: ## Pull the three LANTERN models
	@for m in $(MODELS); do echo "pulling $$m"; $(OLLAMA) pull $$m || exit 1; done

doctor: ## Check Ollama, models and config
	uv run python scripts/doctor.py

lesson: ## Run one lesson: make lesson N=05 [TIER=hosted] [RECORD=1 | REPLAY=1]
	@test -n "$(N)" || (echo "usage: make lesson N=01" && exit 2)
	$(LESSON_ENV) uv run $(if $(filter hosted,$(TIER)),--extra cloud) python lessons/$(N)-*/run.py $(ARGS)

lessons: ## Run every lesson in order
	@for d in lessons/[0-9][0-9]-*/; do uv run python $$d/run.py || exit 1; done

shots: ## Re-run every lesson and save terminal screenshots to docs/screenshots
	@for d in lessons/[0-9][0-9]-*/; do uv run python $$d/run.py --shot || exit 1; done
	uv run python scripts/svg_to_png.py

charts: ## Rebuild the charts in docs/charts from live model runs
	uv run python scripts/make_charts.py

diagrams: ## Render the D2 diagrams in docs/diagrams to SVG
	@n=0; for f in docs/diagrams/*.d2; do d2 --theme 0 --pad 20 "$$f" "$${f%.d2}.svg" >/dev/null || exit 1; n=$$((n+1)); done; \
	 test $$n -gt 0 || (echo "diagrams: no .d2 files found" && exit 1); echo "diagrams: rendered $$n"

eval: ## Run the promptfoo evals against the local models
	cd evals && $(PROMPTFOO) eval --no-cache -c promptfooconfig.yaml --output output/results.json; \
	 status=$$?; cd .. && uv run python scripts/clean_eval_output.py; \
	 if [ $$status -eq 100 ]; then echo "eval: finished, some tests failed (expected: chapter 19 reads them)"; status=0; fi; exit $$status

judge-calibrate: ## Check the eval's judge (qwen3:4b) against labelled answers, live
	uv run python evals/judge/calibrate.py

eval-view: ## Open the promptfoo results viewer at http://localhost:15500
	cd evals && $(PROMPTFOO) view --yes

shots-promptfoo: ## Screenshot the promptfoo viewer (run `make eval-view` in another terminal first)
	uv run python scripts/shoot_promptfoo.py

check: lint test prose structure ## Every offline gate: lint, tests, prose, structure

release-check: check notebooks-check ## Every gate, notebooks current, practice and capstone complete
	uv run python scripts/check_lessons.py --release

hosted-check: ## Live, needs a key: chapter 08 end to end on the hosted tier, checked
	uv run --extra cloud python scripts/hosted_check.py

lint: ## Ruff
	uv run ruff check src scripts lessons tests evals capstone conftest.py

test: ## Unit tests (no model needed)
	uv run pytest -q

prose: ## No em or en dashes in any Markdown or Python file
	uv run python scripts/lint_prose.py

structure: ## Every lesson has the required sections and a run.py
	uv run python scripts/check_lessons.py

smoke: ## Live tests against Ollama
	uv run pytest -q -m live

quiz: ## The chapter check, with why after each answer: make quiz N=05
	@uv run python scripts/learn.py quiz $(N)

exercise: ## Grade your practice/exercise.py, offline: make exercise N=05
	@uv run python scripts/learn.py exercise $(N)

exercise-reset: ## Put a chapter's exercise.py back to the starting stub: make exercise-reset N=05
	git checkout -- lessons/$(N)-*/practice/exercise.py

hint: ## The next hint for a chapter's exercise: make hint N=05
	@uv run python scripts/learn.py hint $(N)

solution: ## The reference solution, once you have tried: make solution N=05
	@uv run python scripts/learn.py solution $(N) $(ARGS)

challenge: ## Break-it challenges, checked against your latest run: make challenge N=05 [TIER=hosted]
	@LANTERN_TIER=$(TIER) ID=$(ID) uv run python scripts/learn.py challenge $(N)

progress: ## Every chapter: predictions, check, exercise, challenges
	@uv run python scripts/learn.py progress

notebooks: ## Build lessons/NN-*/lesson.ipynb from each chapter's README, run.py and practice
	uv run python scripts/build_notebooks.py

notebooks-check: ## Fail if a committed notebook is out of date
	uv run python scripts/build_notebooks.py --check

notebook: ## Open a chapter's notebook in JupyterLab: make notebook N=05
	@test -n "$(N)" || (echo "usage: make notebook N=05" && exit 2)
	uv run --extra notebooks jupyter lab lessons/$(N)-*/lesson.ipynb

capstone: ## Grade your capstone/work/ offline against the capstone tests
	LANTERN_CAPSTONE=learner uv run pytest -q capstone/tests

capstone-solution: ## Run the capstone tests against the reference solution
	uv run pytest -q capstone/tests

capstone-live: ## Run your capstone pipeline live and check it against the recorded thresholds
	uv run python capstone/live_check.py $(ARGS)

clean: ## Remove caches
	rm -rf .pytest_cache .ruff_cache
