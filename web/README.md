<!--
SPDX-FileCopyrightText: 2025 2025 wahl.chat

SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
-->

# Web App

Next.js frontend for [wahl.chat](https://wahl.chat/).

## Setup

### 1. Install dependencies

```bash
bun install
```

### 2. Configure environment variables

```bash
cp .env.example .env.local
```

Fill in the required values in `.env.local`:
- **Backend**: `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8080`. Run the [AI backend](../ai-backend/) locally or point it to a hosted endpoint.
- **Firebase Public and Private Credentials**: Required for the app to function. Obtain from [Firebase Console](https://console.firebase.google.com/) > Project Settings.
- **Stripe**: Optional unless working on donation features.

### 3. Regional election contexts

The app uses geo-detection to redirect users to their regional election context. The mapping is defined in `lib/constants.ts` under `REGION_TO_CONTEXT`.

Each region code (e.g., `HH`) maps to a context ID (e.g., `hh2029`) that must exist in the Firestore `contexts` collection. If a context doesn't exist, users are redirected to the default context (`bundestagswahl-2025`).

## Development

```bash
bun dev
```

Open http://localhost:3000.

## Deployment

Deployed via the [Vercel Platform](https://vercel.com). See the [Next.js deployment docs](https://nextjs.org/docs/app/building-your-application/deploying) for details.

### Cache Revalidation

The app caches Firestore data (sources, parties, contexts) for performance. To revalidate:

```bash
# By cache tag
curl -X POST https://wahl.chat/api/revalidate \
  -H "Authorization: Bearer <REVALIDATE_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"tag": "source_documents"}'

# By path
curl -X POST https://wahl.chat/api/revalidate \
  -H "Authorization: Bearer <REVALIDATE_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"path": "/bundestagswahl-2025/sources"}'
```

Available cache tags (defined in `lib/cache-tags.ts`):
- `source_documents` — Source documents for the sources page
- `parties` — Global party data
- `contexts` — Election contexts
- `context_parties` — Parties per context
- `proposed_questions` — Suggested questions
