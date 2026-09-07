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

Merges to `develop` auto-deploy to [dev.wahl.chat](https://dev.wahl.chat). Production ([wahl.chat](https://wahl.chat)) is a manual **Promote web** GitHub Action so it can ship independently of the backend. That workflow rebuilds the chosen SHA with Production env vars — do not promote a develop preview, because `NEXT_PUBLIC_*` is baked in at build time.

`vercel.json` disables git deploys from `main`. Keep Vercel’s Production Branch set to `main` (unused for auto-deploy) and do not point it at `develop`. See the [root README](../README.md#deploying) and `.github/workflows/promote-web-prod.yml` for the secrets to set.

### Cache Revalidation

Election pages are rendered on request. Firestore election config (contexts, parties, sources, questions) is cached by tag, with a 24h safety TTL. Empty lists and failed reads are not cached, so a context published before its parties does not stay blank. A real-project `seed_firestore.py` run busts those tags when `REVALIDATE_SECRET` is set. Use the secret of the matching Vercel deployment (Production for `ENV=prod` / [wahl.chat](https://wahl.chat), Preview or Development for `ENV=dev` / [dev.wahl.chat](https://dev.wahl.chat)) from [the Vercel env vars page](https://vercel.com/wahl-chat/web/settings/environment-variables). The secret is optional — without it the seed still writes Firestore and warns. The emulator path skips the cache entirely.

To revalidate separately (or after a seed that skipped it):

```bash
REVALIDATE_SECRET=... ENV=prod python firebase/scripts/revalidate_frontend_cache.py
REVALIDATE_SECRET=... ENV=dev python firebase/scripts/revalidate_frontend_cache.py
REVALIDATE_SECRET=... ENV=prod python firebase/scripts/revalidate_frontend_cache.py \
  --context abgeordnetenhauswahl-berlin-2026
```

To revalidate by hand with curl:

```bash
# Tags (preferred — one election, or the coarse tag for every election)
curl -X POST https://wahl.chat/api/revalidate \
  -H "Authorization: Bearer <REVALIDATE_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"tags": ["contexts", "context:abgeordnetenhauswahl-berlin-2026:parties"]}'
```

Single `tag` / `path` keys still work. Tags (defined in `lib/cache-tags.ts`):
- `contexts` — Active election list
- `context:{id}` — One election document
- `context:{id}:parties` / `context_parties` — Parties for one / every election
- `context:{id}:sources` / `source_documents` — Sources for one / every election
- `context:{id}:questions` / `proposed_questions` — Suggested questions
- `parties` — Global party collection (not the per-context list)
