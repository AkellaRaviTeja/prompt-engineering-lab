# Prompt Engineering Lab. Run `make help` for the list.
SHELL := /bin/bash
.DEFAULT_GOAL := help
PROMPTFOO := npx --yes promptfoo@0.124.1
MODELS := qwen3:1.7b qwen3:0.6b qwen3:4b
OLLAMA_HOST ?= http://localhost:11434
# Use the Docker container when it is running, otherwise a native `ollama` binary.
OLLAMA := $(shell docker ps --format '{{.Names}}' 2>/dev/null | grep -qx pel-ollama && echo "docker exec pel-ollama ollama" || echo ollama)

.PHONY: help setup install up up-gpu down models doctor lesson lessons shots charts diagrams \
        eval eval-view shots-promptfoo check lint test prose structure smoke clean

help: ## Show this help
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: install up models doctor ## One command: install, start Ollama, pull models, check
	@echo "Ready. Start with: make lesson N=01"

install: ## Install Python dependencies with uv
	uv sync

up: ## Start Ollama in Docker (CPU)
	docker compose up -d

up-gpu: ## Start Ollama in Docker with an NVIDIA GPU
	docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d

down: ## Stop the Ollama container (models are kept in a volume)
	docker compose down

models: ## Pull the three LANTERN models
	@for m in $(MODELS); do echo "pulling $$m"; $(OLLAMA) pull $$m || exit 1; done

doctor: ## Check Ollama, models and config
	uv run python scripts/doctor.py

lesson: ## Run one lesson: make lesson N=05
	@test -n "$(N)" || (echo "usage: make lesson N=01" && exit 2)
	uv run python lessons/$(N)-*/run.py $(ARGS)

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
	 if [ $$status -eq 100 ]; then echo "eval: finished, some tests failed (expected: chapter 15 reads them)"; status=0; fi; exit $$status

eval-view: ## Open the promptfoo results viewer at http://localhost:15500
	cd evals && $(PROMPTFOO) view --yes

shots-promptfoo: ## Screenshot the promptfoo viewer (run `make eval-view` in another terminal first)
	uv run python scripts/shoot_promptfoo.py

check: lint test prose structure ## Every offline gate: lint, tests, prose, structure

lint: ## Ruff
	uv run ruff check src scripts lessons tests

test: ## Unit tests (no model needed)
	uv run pytest -q

prose: ## No em or en dashes in any Markdown or Python file
	uv run python scripts/lint_prose.py

structure: ## Every lesson has the required sections and a run.py
	uv run python scripts/check_lessons.py

smoke: ## Live tests against Ollama
	uv run pytest -q -m live

clean: ## Remove caches
	rm -rf .pytest_cache .ruff_cache
