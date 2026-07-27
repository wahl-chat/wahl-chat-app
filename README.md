<!--
SPDX-FileCopyrightText: 2026 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# wahl.chat

A grounded political information chatbot for German elections — federal, state, and local.

**Application**: https://wahl.chat/
**About**: https://wahl.chat/about-us
**Press**: https://wahl-chat.notion.site/press

## About

The aim of wahl.chat is to enable users to engage in a contemporary way with the positions of political parties and to receive answers to individual questions that can be substantiated with sources.

## Repository Structure

| Directory | Description | Docs |
|---|---|---|
| [`web/`](web/) | Next.js frontend application | [README](web/README.md) |
| [`ai-backend/`](ai-backend/) | Python AI/RAG backend (FastAPI + SSE + LangChain) | [README](ai-backend/README.md) |
| [`firebase/`](firebase/) | Firebase config, Cloud Functions, Firestore rules & seed data | [README](firebase/README.md) |

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) 22+
- [bun](https://bun.sh/) 1.3.x — install via Homebrew: `brew install bun`, or `curl -fsSL https://bun.sh/install | bash`
- [uv](https://docs.astral.sh/uv/) 0.11.x — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [Docker](https://www.docker.com/) 29+ with Compose v5+
- [Firebase CLI](https://firebase.google.com/docs/cli) 15.x — `npm install -g firebase-tools`

## Local development

No production credentials needed. All data stores run locally.

### 1. Install dependencies

```bash
make install
```

If you use an AI coding assistant, run `./scripts/setup-agent-docs.sh` once to
symlink the provider-specific `CLAUDE.md` to the committed `AGENTS.md` (the
symlink is git-ignored; `AGENTS.md` is the source of truth).

### 2. Configure environment variables

```bash
cp ai-backend/.env.example ai-backend/.env
cp web/.env.example web/.env.local
```

The `.env.example` files are pre-configured for local mode (`QDRANT_URL=http://localhost:6333`, `FIRESTORE_EMULATOR_HOST=localhost:8081`). You only need to fill in LLM API keys (`OPENAI_API_KEY`, `GOOGLE_API_KEY`) for the chat to work.

### 3. Start local data stores

```bash
make stores-up
```

This starts Qdrant via Docker Compose (waiting on `/readyz`, then bootstrapping the collection) and the Firestore + Auth emulators via the Firebase CLI (Firestore on 8081 — avoids the default 8080 clash with the backend — and Auth on 9099). The target waits until the Firestore emulator answers before returning.

For the web app to actually use these emulators (rather than the real project), `web/.env.local` must set `NEXT_PUBLIC_USE_FIREBASE_EMULATORS=true` plus `FIRESTORE_EMULATOR_HOST` / `FIREBASE_AUTH_EMULATOR_HOST` — the `web/.env.example` ships with these enabled. With them set, no service-account key is needed and the browser signs in against the local Auth emulator, so a local session never writes to the real project.

### 4. Seed local data

```bash
FIRESTORE_EMULATOR_HOST=localhost:8081 make seed-local
```

Loads scrubbed fixture data (election contexts, parties, proposed questions) into the local Firestore emulator. The seed script refuses to run without `FIRESTORE_EMULATOR_HOST` set — it will never write to production.

### 5. Start development servers

```bash
make dev
```

Or start everything at once (stores + servers):

```bash
make dev-local
```

This starts both the Next.js frontend (`localhost:3000`) and the Python backend (`localhost:8080`).

### Stopping local stores

```bash
make stores-down
```

### Makefile targets

| Target | Description |
|--------|-------------|
| `make install` | Install all dependencies (web + backend) |
| `make stores-up` | Start Qdrant (Docker) and Firestore emulator (host process) |
| `make stores-down` | Stop all local stores |
| `make seed-local` | Load scrubbed fixtures into local stores (requires `FIRESTORE_EMULATOR_HOST`) |
| `make dev-local` | Start stores + both dev servers |
| `make dev` | Start both dev servers (assumes stores are already running) |
| `make test-backend` | Run backend unit tests |
| `make test-smoke` | Run E2E SSE smoke test |
| `make test-local-mode` | Run the seed-script emulator-guard tests (needs live local stores: `make stores-up` first) |
| `make lint` | Lint web (biome) + backend (ruff) |

## Contributing

We appreciate contributions from our community. Please take a look at the open issues if you are interested.
If you are unsure where to start, please contact robin@wahl.chat.

## License

This project is **source-available** under the [PolyForm Noncommercial 1.0.0](LICENSE) license. Please contact info@wahl.chat for commercial use inquiries.
