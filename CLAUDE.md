<!-- GSD:project-start source:PROJECT.md -->
## Project

**wahl.chat V2 — Data Layer & Foundation**

wahl.chat V2 is the next generation of wahl.chat, a grounded, source-cited political-information chatbot for German elections. This repository forks the existing `wahl-chat-app` (Next.js web frontend + aiohttp/Socket.IO RAG chat backend + Firebase) largely as-is and concentrates new work on the **data layer and ingestion pipeline**: a single, trustworthy, continuously-updated corpus that serves every election (federal, state, local) from one store instead of duplicating content per election.

This first milestone is **foundation + data layer**. New user-facing V2 features (the party matcher's scoring engine, profile/onboarding, proactive chat) are designed-for but **deferred to later milestones**. The team will split the data-source connector work, so this milestone's job is to establish the common ground — shared schema, contracts, pipeline framework, a reference connector, and a fully local dev stack — before everyone builds in parallel.

**Core Value:** One trustworthy corpus, ingested once per source and reused across every election, with a shared data contract solid enough that the team can build connectors in parallel without diverging.

### Constraints

- **Tech stack**: Qdrant stays as the vector store; embeddings stay OpenAI `text-embedding-3-large` (3072-dim) — Why: index parity, mixing models/dimensions breaks the index.
- **Tooling**: uv for Python (`ai-backend`), bun for Node (`web`) — Why: modern, faster; uv requested by lead, bun confirmed as the sole Node package manager (D-08 revert).
- **Transport**: SSE instead of Socket.IO — Why: websockets fail for users behind some corporate networks.
- **Compliance**: GDPR Art. 9 — political opinions are special-category data; explicit consent, EU data residency (`europe-west1`/`europe-west3`), never embedded into the corpus.
- **Ingestion**: must tolerate Firebase's 15-min scheduled-job cap — Why: customer note #5; long jobs need Cloud Run Jobs or chunked/watermarked runs.
- **Dev environment**: local-only data stores during this milestone — Why: avoid corrupting real stores while the design is still settling.
- **Team**: multiple people will build connectors in parallel — Why: drives the "common ground first, then one phase per source" structure.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## 1. Qdrant Collection Design
### Recommended Design: One Collection Per Environment
#### Collection creation (Python, qdrant-client 1.18)
#### Payload indexes to create after collection setup
# party_id: tenant key — is_tenant=True co-locates vectors by party for sequential reads
# region: keyword index for region_path element matching
# authority_tier: keyword index (authoritative | factual_record | self_reported | promotional)
# source_type: keyword index (party_manifesto | vote_record | drucksache | ...)
# publish_date: datetime index for context-window scoping
# source_item_id: keyword/uuid index for per-source lookups and dedup checks
### Cross-Level Query Pattern
# Election context provides these values at query time:
### Deduplication / Idempotent Upserts
# Usage in ingestion:
### Tiered Multitenancy (Qdrant 1.16+, future scaling lever)
### What NOT to Do
- **Do not create one collection per election context** (V1 pattern): cross-context queries require multiple round-trips; shared national docs get duplicated; collection count grows unboundedly.
- **Do not create one collection per party** (V1 namespace pattern): same problems; plus Qdrant's per-collection overhead (RAM for HNSW indexes) multiplies.
- **Do not use a global HNSW (`m != 0`) with `is_tenant` indexing**: building both is wasteful since all queries filter by `party_id`. Set `m=0, payload_m=16`.
- **Do not store `region_path` as an array payload field and try to query "does this array contain X"**: instead store the scalar `region` on the chunk and use `MatchAny` with the election's path at query time.
### Versions (verified)
| Package | Version | Date |
|---------|---------|------|
| Qdrant server | 1.18.2 | 2026-06-04 |
| qdrant-client | 1.18.0 | 2026-05-11 |
| langchain-qdrant | 1.1.0 | 2025-10-22 |
## 2. uv — Python Package Manager
### Decision
### Current Version
### Migration from Poetry
# From the ai-backend directory:
# Run migration tool (no install required — uses uvx temp execution):
# What it does:
# - Rewrites [tool.poetry] → [project] (PEP 621 standard)
# - Rewrites [tool.poetry.dependencies] → [project.dependencies]
# - Moves [tool.poetry.group.dev.dependencies] → [dependency-groups.dev]
# - Deletes poetry.lock
# Regenerate lockfile and install:
# Verify:
### Python Version
- The existing `pyproject.toml` pins `python = ">=3.11 <=3.12"`.
- `langchain-qdrant`, `langchain-google-genai`, and other integration packages have full 3.12 support.
- Python 3.13 requires `numpy>=2.0` which may cascade through the dep tree; this is an unnecessary risk during a migration milestone.
- Bump to 3.13 in a dedicated dependency-update phase after migration is stable.
### Docker Integration
# Layer 1: install dependencies only (cached unless uv.lock changes)
# Layer 2: install the project itself (only re-runs when src/ changes)
# Runtime stage — no uv, no build tools
- `--locked`: fail if `uv.lock` is stale — enforces reproducibility.
- `--no-dev`: exclude dev dependencies (pytest, ruff, mypy) from production image.
- `UV_COMPILE_BYTECODE=1`: moves `.pyc` compilation to image build time → faster cold starts.
### Running Tools Under uv
# Tests
# Linting (ruff is already in [dependency-groups.dev])
# Type checking
# One-off tools without installing globally
### Workspace / Monorepo (Optional)
# Root pyproject.toml
## 3. bun — Node Package Manager
### Decision
The team reverted the briefly-planned package-manager migration (D-08 revert): **bun is the sole Node package manager** for `web/`. `bun.lock` is the committed lockfile.
### Current Version
bun 1.3.14 (install via Homebrew: `brew install bun`).
### CI Rules
- Always `bun install --frozen-lockfile` in CI — never bare `bun install` (it silently re-resolves).
- `bun audit --audit-level=high` is the D-08 supply-chain gate.
### Supply-Chain Hardening (`web/bunfig.toml`)
- `minimumReleaseAge = 604800` — quarantines packages published less than 7 days ago (bun's default is 3 days; set explicitly to preserve the D-08 control).
- `trustedDependencies` in `package.json` allow-lists the only packages permitted to run postinstall scripts.
### Vercel Deployment
Vercel detects `bun.lock` and installs with bun natively — no extra configuration needed.
## 4. Socket.IO → SSE Migration
### Decision
### Backend: FastAPI + sse-starlette
#### Backend implementation pattern
#### Vercel AI SDK data stream protocol (event type reference)
| Event code | Meaning | Data format |
|------------|---------|-------------|
| `f` | Message frame init | `{"messageId": "..."}` |
| `0` | Text token delta | `"token string"` |
| `8` | Data annotation | arbitrary JSON — use for citations |
| `e` | Step finish | `{"finishReason": "stop", "usage": {...}}` |
| `d` | Final summary | `{"finishReason": "stop", "usage": {...}}` |
| `[DONE]` | Stream end | literal string |
- `Content-Type: text/event-stream`
- `x-vercel-ai-ui-message-stream: v1`
- `Cache-Control: no-cache`
- `X-Accel-Buffering: no` (sse-starlette sets this automatically)
### Frontend: useChat with SSE
### Socket.IO Touchpoints to Remove
- `ai-backend/websocket_app.py` → replace with FastAPI `app.py`
- `ai-backend/aiohttp_app.py` → replace main entry point
- `ai-backend/chat_service.py` → adapt stream output to `async_generator`
- `web/components/providers/socket-provider.tsx` → replace with `useChat` provider
- `web/store/actions/initialize-chat-session.ts` → remove socket init
- `web/store/actions/chat-add-user-message.ts` → use `append()` from `useChat`
- `web/store/actions/generate-pro-con-perspective.ts` → adapt to SSE
## 5. Dependency Update Strategy
### Recommended Order
# Targeted upgrade: only the packages we know need updating
# Sync and run tests
# After targeted updates pass — nuclear option for remaining deps:
# Check outdated (non-destructive)
# Interactive upgrade — one major version group at a time
# Type-check after each batch
### CI Gates (Minimum)
### What NOT to Do
- Do not run `uv lock --upgrade` in CI — use `uv sync --locked` to enforce reproducibility.
- Do not use `bun install` without `--frozen-lockfile` in CI — it silently re-resolves.
- Do not update all deps in a single commit — one batch per domain (core framework, AI/LLM, UI, infra) makes bisecting failures practical.
- Do not skip the migration-first, updates-second ordering — mixed failures are intractable.
## Core Technologies (Summary Table)
### Python Stack
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Runtime | Stable; 3.13 deferred; uv manages version |
| uv | 0.11.19 | Package manager | 10–100× faster than Poetry; universal lockfile; OpenAI-backed |
| FastAPI | ≥0.115 | HTTP framework | Replaces aiohttp; ASGI native; type-safe routes; OpenAPI docs |
| sse-starlette | 3.4.4 | SSE streaming | W3C-compliant SSE for FastAPI; handles keep-alive and disconnect |
| qdrant-client | 1.18.0 | Vector store client | Latest; async support; `is_tenant` index support since 1.11 |
| langchain-qdrant | 1.1.0 | LangChain/Qdrant bridge | Latest stable; use for document ingestion convenience |
| langchain | ≥1.2 | LLM orchestration | V1 uses it; keep for chat pipeline |
| langchain-openai | ≥1.1 | OpenAI embeddings | text-embedding-3-large (3072-dim); locked embedding model |
| langchain-google-genai | ≥4.1 | Gemini chat | V1 uses it; keep for generation |
| pydantic | ≥2.10 | Data validation | Already in V1; required by FastAPI |
### Node Stack
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| bun | 1.3.14 | Package manager | Team reverted to bun as the sole Node package manager (see D-08 revert) |
| Next.js | 15.x (keep) | Web framework | V1 baseline; no change this milestone |
| React | 19.x (keep) | UI | V1 baseline; no change |
| Vercel AI SDK (ai) | 5.x + `@ai-sdk/react` 2.x | SSE streaming client | `useChat` (from `@ai-sdk/react`) parses the v5 UI message stream; backend emits matching parts |
### What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Multiple Qdrant collections per election context | Cross-collection queries are limited; duplicates national docs | Single collection with payload filtering |
| `socket.io-client` + `python-socketio` | WebSocket blocked by corporate firewalls; customer confirmed failure | SSE via sse-starlette + Vercel AI SDK useChat |
| Poetry | Slower; non-standard lockfile; migration requested | uv |
| `uv lock --upgrade` in CI | Upgrades everything simultaneously; makes failures unattributable | `uv sync --locked` in CI; targeted upgrades in dev |
| `bun install` without `--frozen-lockfile` in CI | Silently re-resolves; non-reproducible | `bun install --frozen-lockfile` |
| Global HNSW (`m != 0`) with `is_tenant` | Wastes RAM building global index never used in tenant-filtered queries | `m=0, payload_m=16` |
| Python 3.13 this milestone | numpy 2.0 cascade risk; LangChain integration packages may lag | Python 3.12; bump 3.13 in a dedicated dep update phase |
| AI SDK v4 `ai/react` + hand-rolled `data: {code}{json}` frames | v4 parser can't read SSE-framed parts; renders nothing | v5 `@ai-sdk/react` useChat + backend emitting v5 UI-message-stream parts (`data: {"type":...}`) |
## Version Compatibility
| Package | Compatible With | Notes |
|---------|-----------------|-------|
| qdrant-client 1.18 | Qdrant server 1.18.x | Client and server should track same minor version |
| langchain-qdrant 1.1.0 | qdrant-client ≥1.12 | Verified against PyPI requires |
| bun ≥1.3 | Node.js ≥22 | Node 22+ is the supported runtime; drop Node 18/20 in dev environments |
| sse-starlette 3.4.4 | FastAPI ≥0.100, Starlette ≥0.27 | FastAPI ≥0.115 bundles compatible Starlette |
| Vercel AI SDK ai 5.x + `@ai-sdk/react` 2.x | Next.js 15, React 19 | useChat moved to `@ai-sdk/react`; transport via `DefaultChatTransport` |
| uv 0.11.x | Python 3.10–3.13 | Manages Python version via `.python-version` file |
## Installation
### Python (after Poetry → uv migration)
# Install uv (once per machine)
# In ai-backend directory — run migration tool
# Install all dependencies
# Dev workflow
# Add new dependencies
### Node (bun)
# Install bun (once per machine): brew install bun
# In web directory
# Install dependencies (local): bun install
# CI / reproducible installs: bun install --frozen-lockfile
# Dev workflow: bun run dev / bun run lint / bun run build
## Sources
- [Qdrant Multitenancy Documentation](https://qdrant.tech/documentation/manage-data/multitenancy/) — `is_tenant` index, HNSW config, single collection recommendation
- [Qdrant Filtering Documentation](https://qdrant.tech/documentation/search/filtering/) — `MatchAny`, array field semantics
- [Qdrant Points Documentation](https://qdrant.tech/documentation/manage-data/points/) — upsert semantics, UUID point IDs
- [Qdrant 1.16 Release](https://qdrant.tech/blog/qdrant-1.16.x/) — tiered multitenancy, ACORN algorithm
- [qdrant-client PyPI](https://pypi.org/project/qdrant-client/) — version 1.18.0, 2026-05-11
- [langchain-qdrant PyPI](https://pypi.org/project/langchain-qdrant/) — version 1.1.0, 2025-10-22
- [uv GitHub Releases](https://github.com/astral-sh/uv/releases) — version 0.11.19, 2026-06-03
- [uv Docker Integration Guide](https://docs.astral.sh/uv/guides/integration/docker/) — multi-stage Dockerfile pattern
- [migrate-to-uv PyPI](https://pypi.org/project/poetry-to-uv/) — Poetry migration tool
- [Bun Documentation](https://bun.sh/docs) — install, `--frozen-lockfile`, `bunfig.toml` (`minimumReleaseAge`), audit
- [Vercel Package Managers Documentation](https://vercel.com/docs/package-managers) — bun lockfile support
- [Vercel AI SDK Stream Protocols](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol) — data stream v1 format, event types
- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/) — version 3.4.4, 2026-03-29
- [Vercel AI SDK Python Streaming Template](https://vercel.com/templates/next.js/ai-sdk-python-streaming) — FastAPI + useChat integration pattern
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
