.PHONY: help install env dev web-dev build web-build start web-start lint format redis-up redis-down redis-logs chatkit-install chatkit-dev chatkit-clean clean

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
WEB := $(ROOT)/apps/web
CHATKIT := $(ROOT)/services/chatkit
CHATKIT_VENV := $(CHATKIT)/.venv

help:
	@echo "Targets:"
	@echo "  make install     Install dependencies (pnpm)"
	@echo "  make env         Create apps/web/.env.local if missing"
	@echo "  make dev         Run turbo dev (all apps)"
	@echo "  make web-dev     Run Next dev server (apps/web)"
	@echo "  make build       Run turbo build"
	@echo "  make web-build   Build Next app (apps/web)"
	@echo "  make start       Start Next app (apps/web)"
	@echo "  make lint        Run turbo lint"
	@echo "  make format      Run turbo format"
	@echo "  make redis-up    Start Redis via docker compose"
	@echo "  make redis-down  Stop Redis via docker compose"
	@echo "  make redis-logs  Tail Redis logs"
	@echo "  make chatkit-install  Setup Python venv + deps for ChatKit API"
	@echo "  make chatkit-dev      Run ChatKit API server (FastAPI)"
	@echo "  make chatkit-clean    Remove ChatKit virtualenv"
	@echo "  make clean       Remove build outputs"

install:
	pnpm install

env:
	@test -f $(WEB)/.env.local || cp $(WEB)/.env.example $(WEB)/.env.local

dev:
	pnpm dev

web-dev:
	cd $(WEB) && pnpm dev

build:
	pnpm build

web-build:
	cd $(WEB) && pnpm build

start:
	cd $(WEB) && pnpm start

web-start: start

lint:
	pnpm lint

format:
	pnpm format

redis-up:
	docker compose -f $(ROOT)/infra/docker-compose.yml up -d

redis-down:
	docker compose -f $(ROOT)/infra/docker-compose.yml down

redis-logs:
	docker compose -f $(ROOT)/infra/docker-compose.yml logs -f

chatkit-install:
	python3 -m venv $(CHATKIT_VENV)
	$(CHATKIT_VENV)/bin/pip install -r $(CHATKIT)/requirements.txt

chatkit-dev:
	@set -a; \
	if [ -f $(WEB)/.env.local ]; then . $(WEB)/.env.local; fi; \
	set +a; \
	cd $(CHATKIT) && $(CHATKIT_VENV)/bin/uvicorn main:app --reload --port 8000

chatkit-clean:
	rm -rf $(CHATKIT_VENV) $(CHATKIT)/__pycache__

clean:
	rm -rf $(WEB)/.next $(WEB)/dist $(ROOT)/.turbo
