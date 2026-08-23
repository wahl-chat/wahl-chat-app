<!--
SPDX-FileCopyrightText: 2025 wahl.chat

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

The app uses geo-detection to redirect users to their regional election context. `REGION_CONTEXTS` in `lib/constants.ts` keeps each region's context ID and election date together. The context must exist in Firestore; unmapped regions and elections more than five days in the past fall back to `DEFAULT_CONTEXT_ID`.

## Development

```bash
bun dev
```

Open http://localhost:3000.

## Deployment

Deployed via the [Vercel Platform](https://vercel.com). See the [Next.js deployment docs](https://nextjs.org/docs/app/building-your-application/deploying) for details.

### Cache Revalidation

The app caches Firestore data (sources, parties, contexts) for about an hour. A real-project `seed_firestore.py` run busts that cache itself: export `REVALIDATE_SECRET` (same value as this app) and, unless `ENV=prod`, `SITE_URL` or `REVALIDATE_URL`. The emulator path skips this.

To revalidate by hand:

```bash
# One or more cache tags
curl -X POST https://wahl.chat/api/revalidate \
  -H "Authorization: Bearer <REVALIDATE_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"tags": ["context_parties", "contexts"]}'

# One or more paths (layout scope — a context root also busts nested pages)
curl -X POST https://wahl.chat/api/revalidate \
  -H "Authorization: Bearer <REVALIDATE_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"paths": ["/abgeordnetenhauswahl-berlin-2026"]}'
```

Single `tag` / `path` keys still work. Available cache tags (defined in `lib/cache-tags.ts`):
- `source_documents` — Source documents for the sources page
- `parties` — Global party data
- `contexts` — Election contexts
- `context_parties` — Parties per context
- `proposed_questions` — Suggested questions
