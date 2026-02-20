<!--
SPDX-FileCopyrightText: 2025 2025 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# wahl.chat

The leading political information chatbot for the German federal elections 2025.

**Application**: https://wahl.chat/
**About**: https://wahl.chat/about-us
**Press**: https://wahl-chat.notion.site/press

## About

The aim of wahl.chat is to enable users to engage in a contemporary way with the positions of political parties and to receive answers to individual questions that can be substantiated with sources.

## Repository Structure

| Directory | Description | Docs |
|---|---|---|
| [`web/`](web/) | Next.js frontend application | [README](web/README.md) |
| [`ai-backend/`](ai-backend/) | Python AI/RAG backend (aiohttp + Socket.IO + LangChain) | [README](ai-backend/README.md) |
| [`firebase/`](firebase/) | Firebase config, Cloud Functions, Firestore rules & seed data | [README](firebase/README.md) |

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

This project is **source-available** under the [PolyForm Noncommercial 1.0.0](LICENSE) license. Please contact info@wahl.chat for commercial use inquiries.
