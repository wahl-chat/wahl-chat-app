<!--
SPDX-FileCopyrightText: 2025 2025 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# Guided Exploration

This branch contains the guided exploration feature and the accompanying user study platform, built on top of wahl.chat.
In the context of the corresponding masters' thesis, the name guided exploration is equal to structured exploration.

## Setup Overview

### Frontend: [`web/modules/exploration-study/`](web/modules/exploration-study/)

Study flow (consent, tutorial, task, questionnaire, quiz, demographics, debrief). Pages live under
[`web/app/(study)/exploration-study/`](web/app/(study)/exploration-study/).

| Folder        | Description                                                                      |
|---------------|----------------------------------------------------------------------------------|
| `components/` | Components for the study steps: forms, questionnaire, quiz, task, shared, layout |
| `data/`       | Fictitious study parties                                                         |
| `hooks/`      | Timer, per-form-item timing and screen telemetry hooks                           |
| `schemas/`    | Zod schemas for the study forms                                                  |
| `services/`   | Study API client and telemetry service                                           |
| `types/`      | Session, study and form types                                                    |
| `utils/`      | Study state machine (session state → route mapping)                              |

### Frontend: [`web/modules/guided-exploration/`](web/modules/guided-exploration/)

Guided exploration UI: structured, step-by-step comparison of party positions alongside the chat.

| Folder        | Description                                                           |
|---------------|-----------------------------------------------------------------------|
| `components/` | Chat, conversation, exploration-view, shared and layout components    |
| `hooks/`      | Exploration lifecycle/API, SSE and leaf navigation (back/close) hooks |
| `services/`   | Exploration API client and SSE client                                 |
| `store/`      | Zustand store (slices, actions) for exploration state                 |
| `types/`      | Shared frontend types for explorations                                |
| `utils/`      | Case conversion, citation helpers, party marker parsing, tree helpers |

### Backend: [`ai-backend/src/exploration_study/`](ai-backend/src/exploration_study/)

Study backend: sessions, condition counterbalancing, quiz sampling/scoring, exposure logging, Prolific integration.

| Folder      | Description                                                                          |
|-------------|--------------------------------------------------------------------------------------|
| `api/`      | REST routes (participant + admin) and DTOs                                           |
| `models/`   | Session, study, quiz, telemetry and state models                                     |
| `services/` | Session/study repositories, quiz sampler, condition counterbalancer, exposure logger |
| `facade.py` | Module entry point                                                                   |

### Backend: [`ai-backend/src/guided_exploration/`](ai-backend/src/guided_exploration/)

Guided exploration backend: LLM agent pipeline, RAG services, SSE API.

| Folder           | Description                                                                                                                                       |
|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| `agents/`        | LLM agents (topic scout, hierarchy builder, position extractor, leaf content/conversation, classifiers, summaries), each with interface + prompts |
| `api/`           | REST routes, SSE endpoint and DTOs                                                                                                                |
| `handlers/`      | Inbound message routing and flow handlers (exploration lifecycle, navigation, leaf conversation, analysis, baseline)                              |
| `models/`        | Exploration tree, positions, navigation, session, conversation and streaming event models                                                         |
| `services/`      | Orchestrator, session/navigation state stores, RAG services, streaming, citation utils                                                            |
| `composition.py` | Dependency wiring with `facade.py` as the module entry point                                                                                      |

## Setup

Setup is the same as for the main project (see [Getting Started](#getting-started) below):

```bash
make install
cp web/.env.example web/.env.local
cp ai-backend/.env.example ai-backend/.env
make dev
```

Once both servers are running, the guided exploration is available at `http://localhost:3000/{context-id}/explore`

The original project README follows below.

---

# wahl.chat

The leading political information chatbot for the German federal elections 2025.

**Application**: https://wahl.chat/
**About**: https://wahl.chat/about-us
**Press**: https://wahl-chat.notion.site/press

## About

The aim of wahl.chat is to enable users to engage in a contemporary way with the positions of political parties and to
receive answers to individual questions that can be substantiated with sources.

## Repository Structure

| Directory                    | Description                                                   | Docs                           |
|------------------------------|---------------------------------------------------------------|--------------------------------|
| [`web/`](web/)               | Next.js frontend application                                  | [README](web/README.md)        |
| [`ai-backend/`](ai-backend/) | Python AI/RAG backend (aiohttp + Socket.IO + LangChain)       | [README](ai-backend/README.md) |
| [`firebase/`](firebase/)     | Firebase config, Cloud Functions, Firestore rules & seed data | [README](firebase/README.md)   |

## Getting Started

### Prerequisites

- [Node.js](https://nodejs.org/) 18+ and [Bun](https://bun.sh/) (for `web/`)
- [Python](https://www.python.org/) 3.11+ and [Poetry](https://python-poetry.org/) (for `ai-backend/`)
- [Firebase CLI](https://firebase.google.com/docs/cli) (for `firebase/`)

### 1. Install dependencies

```bash
make install
```

### 2. Configure environment variables

```bash
cp web/.env.example web/.env.local
cp ai-backend/.env.example ai-backend/.env
```

See sub-project READMEs for details on required variables.

### 3. Run development servers

```bash
make dev
```

This starts both the Next.js frontend (`localhost:3000`) and the Python backend (`localhost:8080`).

## Contributing

We appreciate contributions from our community. Please take a look at the open issues if you are interested.
If you are unsure where to start, please contact robin@wahl.chat.

## License

This project is **source-available** under the [PolyForm Noncommercial 1.0.0](LICENSE) license. Please contact
info@wahl.chat for commercial use inquiries.
