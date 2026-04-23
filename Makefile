# Development convenience targets for the wahl.chat monorepo

.PHONY: dev dev-web dev-backend install install-web install-backend lint lint-web lint-backend test-backend auth seed seed-prod

# --- Install dependencies ---

install: install-web install-backend

install-web:
	cd web && bun install

install-backend:
	cd ai-backend && poetry install

# --- Development servers ---

dev:
	$(MAKE) -j2 dev-web dev-backend

dev-web:
	cd web && bun run dev

dev-backend:
	cd ai-backend && poetry run python -m src.aiohttp_app

# --- Linting ---

lint: lint-web lint-backend

lint-web:
	cd web && bun run lint

lint-backend:
	cd ai-backend && poetry run ruff check src/

# --- Testing ---

test-backend:
	cd ai-backend && poetry run pytest

# --- Data seeding ---

seed:
	cd ai-backend && poetry run python ../firebase/scripts/seed_firestore.py

seed-prod:
	cd ai-backend && ENV=prod poetry run python ../firebase/scripts/seed_firestore.py

# --- Authentication ---

auth:
	gcloud auth application-default login
	gcloud config set project wahl-chat-dev
