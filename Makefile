# Development convenience targets for the wahl.chat monorepo

.PHONY: dev dev-web dev-backend install install-web install-backend \
        lint lint-web lint-backend test-backend test-smoke test-local-mode \
        stores-up stores-down seed-local dev-local auth bootstrap-collection \
        run-abgeordnetenwatch-votes run-all-landtage-votes run-speeches \
        run-manifestos collect-speeches fetch-mdb-stammdaten \
        update-speeches speeches-stats

# --- Install dependencies ---

install: install-web install-backend

install-web:
	cd web && bun install

install-backend:
	cd ai-backend && uv sync

# --- Local data stores ---

# --project demo-wahl-chat: the emulator MUST run under the same project the web
# app and seed script use (web/.env NEXT_PUBLIC_FIREBASE_PROJECT_ID). Otherwise
# the emulator's configured project (.firebaserc default) differs from the app's;
# the in-memory store serves both namespaces so seeding appears to work, but
# export/import only covers the configured project and silently drops the app's
# data. The demo- prefix is Firebase's offline-only demo-project convention.
#
# Data persists across restarts via --import/--export-on-exit: seeded fixtures
# survive `stores-down`, so the Next.js server's first fetch sees real data
# instead of an empty store. Export happens on clean shutdown (SIGTERM from
# stores-down); a first run with no export metadata starts empty — Firebase
# warns and continues.
EMULATOR_PROJECT ?= demo-wahl-chat
stores-up:
	docker compose up -d qdrant
	mkdir -p firebase/.emulator-data
	cd firebase && nohup firebase emulators:start --project $(EMULATOR_PROJECT) --only firestore,auth --import=.emulator-data --export-on-exit=.emulator-data > ../firebase-emulators.log 2>&1 &
	@echo "Waiting for Qdrant on localhost:6333 (max 30s) ..."
	@for i in $$(seq 1 30); do \
		if curl -sf http://localhost:6333/readyz > /dev/null 2>&1; then \
			echo "Qdrant is ready."; \
			break; \
		fi; \
		if [ $$i -eq 30 ]; then \
			echo "ERROR: Qdrant not ready after 30s — see 'docker compose logs qdrant'" >&2; \
			exit 1; \
		fi; \
		sleep 1; \
	done
	@echo "Waiting for the Firestore emulator on localhost:8081 (max 30s) ..."
	@for i in $$(seq 1 30); do \
		if curl -s -o /dev/null http://localhost:8081 2>/dev/null; then \
			echo "Firestore emulator is ready."; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "ERROR: Firestore emulator not ready after 30s — see firebase-emulators.log" >&2; \
	exit 1

# --- Ingestion target store ---
# Collection setup and every ingestion run default to the local Qdrant container.
# Override these to target a deployed store (there is no scheduled orchestration
# yet). Export the API key in the shell (e.g. from a secret file) rather than
# writing it on the command line:
#   export QDRANT_API_KEY=...   # or: set -a; source secrets.env; set +a
#   make run-speeches QDRANT_URL=https://<host>:6333 ENV=prod
# ENV scopes the collection name (wahlchat_chunks_{ENV}); dev and prod are isolated.
QDRANT_URL ?= http://localhost:6333
ENV ?= dev
# QDRANT_API_KEY is unset by default (local Qdrant is unauthenticated) and is
# exported into the recipe environment instead of being interpolated into the
# recipe text: make echoes recipes (and `make -n` prints them), so a key in
# QDRANT_ENV would leak into terminal/CI logs. Export only when non-empty, so
# an empty string never reaches the client as a bogus credential.
ifneq ($(QDRANT_API_KEY),)
export QDRANT_API_KEY
endif
QDRANT_ENV := QDRANT_URL=$(QDRANT_URL) ENV=$(ENV)

# bootstrap-collection: create the Qdrant collection (wahlchat_chunks_{ENV}) if
# it does not exist. Idempotent — setup_collection is a no-op when the collection
# already matches. A fresh Qdrant volume has no collection, so the runner's first
# get_cursor() call 404s without this. Run after stores-up (Qdrant must be ready).
bootstrap-collection:
	cd ai-backend && $(QDRANT_ENV) uv run python -m src.ingestion.setup_collection

stores-down:
	docker compose down
	pkill -f "firebase emulators" || true

seed-local:
	@test -n "$(FIRESTORE_EMULATOR_HOST)" || (echo "ERROR: FIRESTORE_EMULATOR_HOST not set — set it to localhost:8081 before seeding" && exit 1)
	cd ai-backend && FIRESTORE_EMULATOR_HOST=$(FIRESTORE_EMULATOR_HOST) uv run python ../firebase/scripts/seed_firestore.py

dev-local: stores-up bootstrap-collection
	$(MAKE) -j2 dev-web dev-backend

# --- Development servers ---

dev:
	$(MAKE) -j2 dev-web dev-backend

dev-web:
	cd web && bun run dev

dev-backend:
	cd ai-backend && uv run python -m src.app

# --- Linting ---

lint: lint-web lint-backend

lint-web:
	cd web && bun run lint

lint-backend:
	cd ai-backend && uv run ruff check src/

# --- Testing ---

test-backend:
	cd ai-backend && uv run pytest tests/ --ignore=tests/test_chat_sse.py --ignore=tests/test_local_mode.py

test-smoke:
	cd ai-backend && uv run pytest tests/test_chat_sse.py -x

# test-local-mode: exercises the seed-script FIRESTORE_EMULATOR_HOST guard
# end-to-end. Deliberately NOT part of CI or test-backend — it needs
# LIVE local stores: run `make stores-up` first.
test-local-mode:
	cd ai-backend && uv run pytest tests/test_local_mode.py -x

# --- Ingestion connector run targets (Makefile is the interim scheduler) ---
# Cloud Scheduler is deferred to a planned Terraform deployment workstream (infra/).
# These targets invoke the same src.ingestion.run entrypoint; they default to the
# local Qdrant container but target a deployed store when QDRANT_URL / QDRANT_API_KEY
# / ENV are overridden (see the QDRANT_ENV block above).
# Requires: make stores-up first for local runs.

run-abgeordnetenwatch-votes: bootstrap-collection
	cd ai-backend && $(QDRANT_ENV) uv run python -m src.ingestion.run --connector abgeordnetenwatch_votes

# run-all-landtage-votes: loops the connector over all 16 Landtag legislature IDs (run
# selectivity).  IDs are sourced from LANDTAG_LEGISLATURE_IDS in legislature_config.py so the
# list stays single-sourced in config — no hardcoded integers in the Makefile.
# Each iteration passes AW_LEGISLATURE_ID=<id> to a subprocess so the connector's
# module-level _DEFAULT_LEGISLATURE_ID reads the correct value at import time.
# Requires: make stores-up first; AW_API_KEY in ai-backend/.env if rate-limited.
# Each iteration runs in a subshell; a failure (e.g. zero-poll fail-fast
# on a newly-constituted Landtag) is recorded but does NOT abort the remaining
# legislatures. After the loop, failed IDs are summarised and the target exits
# non-zero so CI / the operator sees the partial failure instead of it being
# swallowed by the last iteration's exit status.
run-all-landtage-votes: bootstrap-collection
	@failed=""; \
	for id in $$(cd ai-backend && uv run python -c \
	    "from src.ingestion.connectors.abgeordnetenwatch.legislature_config import LANDTAG_LEGISLATURE_IDS; print(*LANDTAG_LEGISLATURE_IDS)"); do \
	    echo "=== Landtag legislature_id=$$id ==="; \
	    if ! (cd ai-backend && AW_LEGISLATURE_ID=$$id $(QDRANT_ENV) \
	        uv run python -m src.ingestion.run --connector abgeordnetenwatch_votes); then \
	        echo "!!! Landtag legislature_id=$$id FAILED"; \
	        failed="$$failed $$id"; \
	    fi; \
	done; \
	if [ -n "$$failed" ]; then \
	    echo "=== run-all-landtage-votes: FAILED legislature ids:$$failed ==="; \
	    exit 1; \
	fi; \
	echo "=== run-all-landtage-votes: all legislatures completed ==="

# fetch-mdb-stammdaten: pre-fetch the MdB-Stammdaten XML (speaker→party lookup
# the speech connectors use) for the host dev loop. The registry speech run
# fetches it on demand at run time, so this target just warms the local cache —
# and it is what the bulk/JSONL backfill paths (which use the tolerant loader)
# rely on. Idempotent: skips if already present (delete it to refresh). The URL
# and download logic live in one place (bundestag_speeches.constants / .mdb).
fetch-mdb-stammdaten:
	cd ai-backend && uv run python -m src.ingestion.connectors.bundestag_speeches.mdb

# Speeches: runs the live incremental BundestagSpeechesConnector via run.py.
# --batch-size and --time-budget flow via ARGS (run.py flags).
# --wahlperiode is NOT a run.py flag — set it via the DIP_WAHLPERIODE env var
# (connector __init__ default 21).
# Requires: a valid DIP_API_KEY in ai-backend/.env; make stores-up first.
run-speeches: bootstrap-collection fetch-mdb-stammdaten
	cd ai-backend && $(QDRANT_ENV) \
		uv run python -m src.ingestion.run --connector bundestag_speeches $(ARGS)

# --- Standalone ingestion scripts (NOT registry connectors) ---
# Manifestos run as their own module (own argparse) — NOT a --connector ID in run.py.
# Self-loads ai-backend/.env (OPENAI_API_KEY) and defaults QDRANT_URL to local.
# Pass script flags via ARGS, e.g.:
#   make run-manifestos ARGS="--ids 367 --limit 1"   # smoke one program
#   make run-manifestos ARGS="--dry-run"             # parse only, zero OpenAI cost
# Requires: make stores-up first.

# Manifestos: embeds party-manifesto chunks into Qdrant. PDFs are downloaded and
# parsed in-memory; HTML manifestos are scraped (main content only). Citations
# point at the original source URL — nothing is stored or re-served, so no
# Firestore is needed. Needs Qdrant only.
run-manifestos: bootstrap-collection
	cd ai-backend && $(QDRANT_ENV) \
		uv run python -m src.ingestion.connectors.manifestos.bulk $(ARGS)

# collect-speeches: optional --from-jsonl backfill that replays speeches.jsonl
# through the relocated corpus mapper without hitting the DIP API.
# JSONL path: positional arg > SPEECHES_JSONL env > repo-root speeches.jsonl.
# No DIP_API_KEY required for the bulk path (JSONL → mapper → embed).
# The MdB-Stammdaten XML is fetched by the fetch-mdb-stammdaten prereq below.
# Requires: make stores-up first; OPENAI_API_KEY in ai-backend/.env.
collect-speeches: bootstrap-collection fetch-mdb-stammdaten
	cd ai-backend && $(QDRANT_ENV) \
		uv run python -m src.ingestion.connectors.bundestag_speeches.bulk $(ARGS)

# --- Scheduled-update emulation targets for bundestag_speeches (Cloud Run Job model) ---
# scheduling deferred to infra/IaC (like AW); run these locally to emulate the daily/weekly Cloud Run incremental update Job.

# SPEECH_BATCH controls the --batch-size cap for update-speeches; override with: make update-speeches SPEECH_BATCH=10
SPEECH_BATCH ?= 25

# update-speeches: mirrors the scheduled Cloud Run incremental update Job for bundestag_speeches.
# Scheduling deferred to infra/IaC, like AW. Requires: make stores-up; DIP_API_KEY in ai-backend/.env.
update-speeches: bootstrap-collection fetch-mdb-stammdaten
	cd ai-backend && $(QDRANT_ENV) \
		uv run python -m src.ingestion.run --connector bundestag_speeches --batch-size $(SPEECH_BATCH)

# speeches-stats: quick read-only Qdrant verification for parliamentary_speech.
# Prints total chunk count, count with external_id set, and current cursor (max external_id).
speeches-stats:
	cd ai-backend && $(QDRANT_ENV) \
		uv run python -c "\
import os; \
from src.ingestion.setup_collection import COLLECTION_NAME; \
from src.ingestion.run import get_cursor; \
from qdrant_client import QdrantClient, models; \
c = QdrantClient(url=os.environ.get('QDRANT_URL', 'http://localhost:6333'), api_key=os.environ.get('QDRANT_API_KEY')); \
total = c.count(COLLECTION_NAME, count_filter=models.Filter(must=[models.FieldCondition(key='source_type', match=models.MatchValue(value='parliamentary_speech'))]), exact=True).count; \
with_ext = c.count(COLLECTION_NAME, count_filter=models.Filter(must=[models.FieldCondition(key='source_type', match=models.MatchValue(value='parliamentary_speech'))], must_not=[models.IsNullCondition(is_null=models.PayloadField(key='external_id'))]), exact=True).count; \
cursor = get_cursor(c, COLLECTION_NAME, 'parliamentary_speech'); \
print(f'parliamentary_speech total chunks : {total}'); \
print(f'chunks with external_id set       : {with_ext}'); \
print(f'current cursor (max external_id)  : {cursor}') \
"

# --- Authentication (prod only — NOT used in local mode) ---

auth:
	gcloud auth application-default login
	gcloud config set project wahl-chat-dev
