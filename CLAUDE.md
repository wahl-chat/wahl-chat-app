# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

wahl.chat is a political information chatbot for the German federal elections 2025. Users can chat with party programs, ask questions about political topics, and get party positions with sources.

## Commands

```bash
pnpm dev          # Start development server (localhost:3000)
pnpm build        # Production build
pnpm lint         # Run ESLint + Biome linting
pnpm lint:fix     # Auto-fix lint issues
pnpm format       # Format code with Biome
```

## Architecture

### State Management

Two Zustand stores power the application:

- **ChatStore** (`lib/stores/chat-store.ts`): Main chat functionality with streaming messages, party responses, sources, voting behavior. Uses immer middleware. Actions are split into individual files in `lib/stores/actions/`.
- **AgentStore** (`lib/stores/agent-store.ts`): Multi-step agent flow (consent → data-collection → topic-selection → chat → completed). Simpler vanilla Zustand store.

Both stores are provided via React context (`components/providers/*-store-provider.tsx`).

### Real-time Communication

WebSocket communication via Socket.IO (`lib/chat-socket.ts`, `components/providers/socket-provider.tsx`). Events include:
- `sources_ready`, `party_response_chunk_ready`, `party_response_complete` for streaming responses
- `quick_replies_and_title_ready` for chat suggestions
- `pro_con_perspective_complete`, `voting_behavior_*` for additional features

Backend URL configured via `NEXT_PUBLIC_API_URL` environment variable.

### Firebase Integration

- `lib/firebase/firebase.ts`: Client-side Firebase (auth, Firestore)
- `lib/firebase/firebase-admin.ts`: Server-side admin SDK
- `lib/firebase/firebase-server.ts`: Server actions for data fetching (parties, tenants, users)

### Key Patterns

- **Path aliases**: Use `@/` for imports (enforced by ESLint rule `no-relative-import-paths`)
- **UI Components**: shadcn/ui components in `components/ui/`
- **Providers hierarchy** (in order): AuthServiceWorker → Tooltip → AnonymousAuth → Tenant → Theme → Parties → Socket → ChatStore

### Route Groups

- `app/(with-header)/`: Pages with standard header (chat, about, legal pages)
- `app/(custom-header)/`: Pages with custom header handling
- `app/agent/`: Agent flow pages
- `app/api/`: API routes (agent, embed, parties, revalidation)

## Code Style

- Single trailing blank line at the end of files
- Biome for formatting (2-space indent, single quotes, trailing commas)
- ESLint with Next.js + Tailwind plugins
- German UI text throughout the application

## Git Use
- Never commit or push anything unless stated or approved by the user.
- Never add claude code as co-author of the commits (unless stated otherwise).
- Don't say that the commit was generated using claude code.