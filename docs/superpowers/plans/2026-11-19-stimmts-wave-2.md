# Stimmt's? wave 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the canvas Robin approved on 19.11.2026: a compact Stimmt's? card on the News feed, a header icon after the first game, a game-first start screen in the feed's look with short sourced key points, a feed-style result, a share link that challenges the friend, and the chat card (built, hidden).

**Architecture:** Rules stay in pure, tested functions under `web/lib/stimmts/`; UI stays in `web/components/stimmts/`, except the feed card and header icon, which live with the feed in `web/components/daily/`. The game moves into the feed's route group `app/(wide)/` so it shares the feed's header and `.daily-theme` tokens. The feed page is ISR-cached, so everything that depends on the player's device (played today, countdown, "Neu") is decided in the browser: an inline head script marks the `<html>` element before first paint, CSS hides or shows on that mark, and date-dependent text fills fixed-size slots after mount.

**Tech Stack:** Next.js 15 / React 19, TypeScript, Tailwind, `bun test`, biome, `motion/react` (`useReducedMotion`), Firestore (`system_status/stimmts`).

**Spec:** the canvas https://claude.ai/artifact/DyMi86VNHgZvSN2H2r5CU6 (version 1795106364-eb7e; board names in quotes below), plus `docs/superpowers/specs/2026-11-13-stimmts-feedback-round-design.md` for the rules it does not change. Read the boards named in your task before you start; the canvas is the source for copy, sizes and order.

## Global Constraints

- Players predict; no copy may suggest they vote.
- Party colours, party logos and vote dots are never changed.
- Key points, briefings and short names are neutral and never hint at the result.
- `PROGRESS_VERSION` and the stored progress shape stay as they are.
- "Rätsel" is "Quiz" in all user-facing copy ("Tagesquiz", "Nächstes Quiz in …", "Jeden Tag ein neues Quiz"). The name "Stimmt's?" stays.
- Everything works in dark and light (`.daily-theme` tokens, `--daily-*`), at 320 px, by keyboard and screen reader, and with reduced motion (no movement when "Bewegung reduzieren" is on; fades are fine).
- At 375 × 667 "Los geht's" is always on screen on the start screen, including with "Mehr Info" open.
- Off is the default: the feed card and the header icon show only when `system_status/stimmts` is on and today has a puzzle. The feed must load when that read fails.
- No layout shift on `/`: the feed card's height is fixed on the server render.
- Code, identifiers and comments in English; copy in German; comments explain why (see `AGENTS.md`).
- Verify with `cd web && bun run test`, `bun run lint`, `bun run typecheck`. Never `bun run build` while a dev server runs (check `lsof -nP -iTCP:3000 -sTCP:LISTEN`).
- Parked, not built: rewards, styles ("Papier", "Kuppel", "Nacht", "Festlich", "Gold"), the "Tag N" streak, the option "direkt zum Tippen" ("B2-Direkt").
- Commits: one per task on the task's branch, message ending with the `Co-Authored-By` line; no push and no PR change without Miquel's go.

## Review Focus

1. **Longest content at 320 px.** The longest `yesMeans` (96 characters) plus three 12-word key points must not slide under the pinned "Los geht's" bar; the longest `shortName` must fit the feed card in at most two lines. Pinned by the 22-character `shortName` rule (Task 2) and the 320 px browser checks in Tasks 5 and 11.
2. **Berlin midnight on an open or cached feed.** The ISR page may be hours old. The card must show today's short name and countdown, and yesterday's played state must not hide today's card. Pinned by `feedEntry` tests at 23:59:59 and 00:00:01 (Task 10).
3. **Storage that throws or holds junk.** Private mode, blocked storage, or an old/corrupt progress value: the head script must not throw and must leave the card in its "before" state with no icon. Pinned by the script tests in Task 10.
4. **Switch off or Firestore unreachable on `/`.** No card, no icon, the feed renders. Pinned by the `feedEntry` "off → hidden" test and the `getStimmtsStatus` error test in Task 10, and the blocked-Firestore browser check in Task 11.
5. **Share links anyone can type.** `s` out of range, a `d` that is not today, or a visitor who already played today: no banner. Pinned by `shareChallenge` tests in Task 6.

## Decisions taken in this plan (not on the canvas)

- **Stimmkarte:** feed style ("Stimmkarte (Feed-Stil)"), not "Tinte". The urn and the Wahlperiode block stay on the result screen, below the vote card, unchanged.
- **Back side ("Mehr Info"):** shows what the content has today: the full `briefing`, then "Das Dokument" (type, official title, vote date and version) with the PDF links and "Zusammenfassung von wahl.chat". The headed sections on "Rückseite: Mehr Info" ("Was ändert sich", "Was es kostet", …) need new content for all 30 puzzles and are a follow-up.
- **"Mehr Info":** expands in place on phones (`< md`) and swaps the card to its back side on desktop (`md+`); both keep "Los geht's" on screen.
- **Share-link banner** only when the link's day `d` is today in Berlin, so the friend plays the same puzzle the score was for.
- **Server-side status for `/`:** `getStimmtsStatus()` reads `system_status/stimmts` with a 5-minute cache, so the card is in the first HTML when the game is on. The live listener still hides it at once when the switch goes off.
- **`shortName`:** a new required field, with article, at most 22 characters ("Der Tankrabatt").

---

## Execution layout

| Task | Who | Depends on | Branch |
| --- | --- | --- | --- |
| 1 Key point sources + short names (content) | content agent, Miquel approves | – | main checkout, docs only |
| 2 Content schema: sourced key points, `shortName` | implementer + reviewer | 1 | `stimmts/sourced-key-points` |
| 3 "Quiz" wording in code and docs | implementer + reviewer | – | `stimmts/quiz-wording` |
| 4 Game in the feed shell | implementer + reviewer | – | `stimmts/feed-shell` |
| 5 Start screen | implementer + reviewer | 2, 3, 4 | `stimmts/start-screen` |
| 6 Share-link banner | implementer + reviewer | 5 | `stimmts/share-banner` |
| 7 Share text and image | implementer + reviewer | 3 | `stimmts/share-image` |
| 8 Result screen | implementer + reviewer | 3, 4 | `stimmts/result-look` |
| 9 Chat card (hidden) | implementer + reviewer | 8 | `stimmts/chat-card` |
| 10 Feed entry rules + presence script | implementer + reviewer | 2 | `stimmts/feed-entry-rules` |
| 11 Feed card on `/` | implementer + reviewer | 10 | `stimmts/feed-card` |
| 12 Header icon + fly-in | implementer + reviewer | 11 | `stimmts/header-icon` |
| 13 Whole-branch review | reviewer | all | – |

Tasks 1, 3, 4 start in parallel; 7 and 10 as soon as their inputs land. Claude merges each reviewed branch into `feat/stimmts` with `git merge --no-ff`.

---

### Task 1: Key point sources and short names (content)

**Files:**
- Modify: `docs/stimmts/key-points-drafts.md`
- Create: `docs/stimmts/short-names-drafts.md`

**Interfaces:**
- Produces: for each of the 30 puzzle ids, three key points without `**`, each with exactly one source `Drucksache · page`, and one `shortName`. Task 2 copies them into `puzzles.json`.

- [ ] **Step 1: Rewrite each key point without emphasis and give it one source.** Per bullet: the text with `**` removed, then ` — Quelle: 21/8157 S. 418`. The source is the page that proves the bullet's number or claim, taken from the existing "Quelle:" line of that puzzle. The Drucksache must be the puzzle's `document.number` or `document.votedIn.number`; `uebergewinnsteuer` has no `document`, so name the Drucksache its "Quelle:" line uses.
- [ ] **Step 2: Write `short-names-drafts.md`.** One line per puzzle: `` `id` — Der Tankrabatt ``. Rules at the top of the file: article + noun phrase, at most 22 characters, everyday words, no verb, no hint at the result, reads after "Heute: ".
- [ ] **Step 3: Check.** Every page opened in the PDF; every short name counted. Mark anything unverified "ungeprüft".
- [ ] **Step 4: Miquel approves both files.** Nothing goes into `puzzles.json` before that.

### Task 2: Content schema — sourced key points and `shortName`

**Files:**
- Modify: `web/lib/stimmts/types.ts`, `web/lib/stimmts/validate.ts`, `web/lib/stimmts/validate.test.ts`, `web/lib/stimmts/content/puzzles.json`, `docs/stimmts/CONTENT.md`
- Create: `web/lib/stimmts/drucksache.ts`, `web/lib/stimmts/drucksache.test.ts`
- Delete: `web/lib/stimmts/emphasis.ts`, `web/lib/stimmts/emphasis.test.ts`

**Interfaces:**
- Produces:
  - `type KeyPointSource = { document: string; page: number }` (`document` like `"21/8157"`)
  - `type KeyPoint = { text: string; source: KeyPointSource }`
  - `Puzzle.keyPoints?: [KeyPoint, KeyPoint, KeyPoint]`, `Puzzle.shortName: string`
  - `drucksachePdfUrl(number: string): string`
  - `keyPointSourceUrl(source: KeyPointSource): string` (PDF URL + `#page=N`)
  - `keyPointSourceLabel(source: KeyPointSource): string` → `"21/8157 · S. 418"`
  - `keyPointSourceAria(source: KeyPointSource): string` → `"Quelle: Drucksache 21/8157, Seite 418"`

- [ ] **Step 1: Write the failing tests** in `drucksache.test.ts`:

```ts
expect(drucksachePdfUrl('21/8157')).toBe('https://dserver.bundestag.de/btd/21/081/2108157.pdf');
expect(drucksachePdfUrl('21/6561')).toBe('https://dserver.bundestag.de/btd/21/065/2106561.pdf');
expect(drucksachePdfUrl('21/134')).toBe('https://dserver.bundestag.de/btd/21/001/2100134.pdf');
expect(keyPointSourceUrl({ document: '21/8157', page: 418 })).toBe('https://dserver.bundestag.de/btd/21/081/2108157.pdf#page=418');
expect(keyPointSourceLabel({ document: '21/8157', page: 4 })).toBe('21/8157 · S. 4');
expect(keyPointSourceAria({ document: '21/8157', page: 4 })).toBe('Quelle: Drucksache 21/8157, Seite 4');
```

and in `validate.test.ts`, each refused with a message naming the puzzle id: key point as a plain string; `text` containing `*`; `text` over 12 words; `page` 0, negative or not an integer; `document` not matching `/^\d{2}\/\d{1,5}$/`; `document` not equal to `document.number` or `document.votedIn.number` when the puzzle has a `document`; `shortName` missing, empty, over 22 characters, or not starting with `Der `, `Die ` or `Das `. One valid puzzle with all of these passes.

- [ ] **Step 2: Run** `cd web && bun test lib/stimmts/drucksache.test.ts lib/stimmts/validate.test.ts` — expect FAIL (module missing, old shape accepted).
- [ ] **Step 3: Implement** `drucksache.ts` (number padded to 5 digits; folder = its first 3 digits) and the validator changes (`readKeyPoint` reads `{ text, source }`; new `readShortName`). Remove `emphasis.ts`, its test, and every import of it.
- [ ] **Step 4: Migrate `puzzles.json`** from the approved drafts (Task 1) with a one-off script in the scratchpad, not committed: `keyPoints` become objects, `shortName` goes after `title`. Run `bunx biome format --write lib/stimmts/content/puzzles.json`.
- [ ] **Step 5: Run** `bun run test && bun run typecheck` — expect PASS (content validates at module load, so a bad entry fails every test).
- [ ] **Step 6: Update `CONTENT.md`** (key point rules, sources, short name rules) and commit: `feat(stimmts): source each key point and add short names`.

### Task 3: "Quiz" wording in code and docs

**Files:**
- Modify: every user-facing string in `web/components/stimmts/`, `web/lib/stimmts/` (share text, labels, aria-labels, page metadata in `app/(with-header)/stimmts/page.tsx` (in `app/(wide)/` once Task 4 lands; whichever merges second resolves the move) and `app/stimmts/share/route.tsx`), tests that assert those strings, `docs/stimmts/*.md`, and the Stimmt's? section of `AGENTS.md`.

**Interfaces:**
- Produces: no new names. `Countdown`'s default label becomes `'Nächstes Quiz in'`.

- [ ] **Step 1: List the hits:** `grep -rn "Rätsel" web/components/stimmts web/lib/stimmts web/app docs/stimmts AGENTS.md`. Identifiers stay English and are not renamed.
- [ ] **Step 2: Update the tests first** that assert copy (`share.test.ts`, `labels.test.ts`, …) to the new words, e.g. `'Das Quiz von wahl.chat: Wie haben die Parteien im Bundestag abgestimmt?'`. Run `bun test` — expect FAIL on exactly those.
- [ ] **Step 3: Replace the copy.** Compounds: "Tagesrätsel" → "Tagesquiz", "Rätsel" → "Quiz" (neuter: "das Quiz", "ein neues Quiz"), "Dieses Rätsel zurücksetzen" → "Dieses Quiz zurücksetzen". Fix articles and adjective endings in each sentence.
- [ ] **Step 4: Run** `bun run test && bun run lint` — expect PASS; `grep -rn "Rätsel"` over the same paths returns only `docs/stimmts/puzzle-selection.md` history, if anything.
- [ ] **Step 5: Commit** `chore(stimmts): call it a Quiz in all copy`.

### Task 4: Game in the feed shell

Boards: all dark/light pairs; "Start 375 × 667, hell".

**Files:**
- Move: `web/app/(with-header)/stimmts/page.tsx` → `web/app/(wide)/stimmts/page.tsx` (URL unchanged)
- Modify: `web/lib/stimmts/fonts.ts` (drop what the feed's `DAILY_THEME_CLASSES` already provides), `web/components/stimmts/status-screen.tsx`, `pill-button.tsx`, and other components that use the game's own colour tokens where a `--daily-*` token exists
- Modify: `web/lib/stimmts/labels.ts`, `web/lib/stimmts/labels.test.ts`

**Interfaces:**
- Produces: `feedDate(isoDate: string): string` → `"Sonntag, 15. November"`; `voteDateShort(isoDate: string): string` → `"25. September"`. `/stimmts` renders under `DailyHeader` inside `.daily-theme`.

- [ ] **Step 1: Write the failing tests** for `feedDate('2026-11-15') === 'Sonntag, 15. November'` and `voteDateShort('2026-09-25') === '25. September'`.
- [ ] **Step 2: Run** `bun test lib/stimmts/labels.test.ts` — expect FAIL.
- [ ] **Step 3: Implement** both in `labels.ts` from `weekdayName` and `formatDate`.
- [ ] **Step 4: Move the route** with `git mv`, keep its metadata, and render `STIMMTS_FONT_CLASSES` only for the game's display font if the feed's Inter does not cover it. Swap the game's grey/ink tokens for `--daily-canvas`, `--daily-surface`, `--daily-border`, `--daily-ink`, `--daily-muted`; party and seat colours stay.
- [ ] **Step 5: Verify** `bun run test && bun run typecheck && bun run lint` PASS; open `/stimmts?day=1` in preview mode in dark and light: feed header on top, no white flash, status screens readable.
- [ ] **Step 6: Commit** `feat(stimmts): run the game in the feed's shell and theme`.

### Task 5: Start screen

Boards: "Start (Baustein)", "Start 375 × 667" (+ hell, gescrollt), "Start 320 px", "Start 375 — Mehr Info aufgeklappt", "Rückseite: Mehr Info" (+ hell), "Start Desktop", "Ablauf 1: Start".

**Files:**
- Create: `web/components/stimmts/start-screen.tsx`, `web/components/stimmts/key-points.tsx`, `web/components/stimmts/more-info.tsx`, `web/components/stimmts/start-bar.tsx`
- Modify: `web/components/stimmts/puzzle-game.tsx` (the `'briefing'` phase renders `StartScreen`), `web/components/stimmts/how-to-play.tsx` (opened from the (i) button)
- Delete once unused: `briefing.tsx`'s `Briefing` (keep `BriefingSheet` only if the result or past-day screen still uses it)
- Create: `web/lib/stimmts/start-view.ts`, `web/lib/stimmts/start-view.test.ts` (the repo has no DOM test setup; component behaviour is checked in the browser in Step 5)

**Interfaces:**
- Consumes: `KeyPoint`, `keyPointSourceUrl/Label/Aria` (Task 2); `voteDateShort` (Task 4); `feedTopicFor` + `TopicDot` from `web/components/daily/topic-chip.tsx`.
- Produces: `StartScreen({ number, puzzle, playDate, banner?: ReactNode, onStart }: Props)` — Task 6 passes `banner`; `briefingFront(puzzle: Puzzle): { kind: 'points'; points: KeyPoint[] } | { kind: 'briefing'; text: string }`; `startMeta(puzzle: Puzzle): { feedTopic: FeedTopic; label: string }` → label `"Energie · 25. September"`.

Layout, top to bottom (copy exact):
1. Row: Stimmt's? logo (`StimmtsLogo`), "Tagesquiz" pill, (i) button `aria-label="So funktioniert’s"` that opens `HowToPlay` (auto-open for a new player stays).
2. Game card: `<h1>` "Rate, wie die 5 Fraktionen abgestimmt haben.", the five party logos each with a "?" (`aria-label="Fünf Fraktionen, noch nicht getippt"`).
3. Briefing card (`CARD_SURFACE`): meta "● {topic} · {voteDateShort}" with the feed topic dot; `<h2>` title; "**Ja** heißt: …" (from `yesMeaning`); label "Kernpunkte"; three bullets, plain text, each followed by a source pill `keyPointSourceLabel` linking to `keyPointSourceUrl` (`target="_blank"`, `aria-label` = `keyPointSourceAria`); button "Mehr Info" / "Weniger anzeigen" with `aria-expanded` and `aria-controls`. A puzzle without `keyPoints` shows the `briefing` paragraph instead of the list.
4. `MoreInfo`: the full `briefing`, "Das Dokument" (`dl`: Art, Amtlicher Titel, Abgestimmt), PDF links for `document` and `votedIn`, "Zusammenfassung von wahl.chat", and "← Zurück zu den Punkten". Below `md` it expands under the bullets; at `md+` it replaces the front of the card. Focus moves to its heading on open and back to "Mehr Info" on close.
5. `StartBar`: "Los geht’s →". Below `md`: `fixed` at the bottom with safe-area padding, and the page gets bottom padding equal to its height. At `md+`: in flow under the card.

Removed: the empty hemicycle, the Stimmkarte at the top, the dots/arrows/half-flip intro.

- [ ] **Step 1: Write the failing tests** in `start-view.test.ts`:
  - `briefingFront` of `tankrabatt-2026` → `kind: 'points'`, three points, the first with `source` `{ document: '21/8157', page: 418 }`;
  - `briefingFront` of a copy without `keyPoints` → `{ kind: 'briefing', text: puzzle.briefing }`;
  - `startMeta` of `tankrabatt-2026` → `{ feedTopic: 'climate_environment', label: 'Energie · 25. September' }`.
- [ ] **Step 2: Run** `bun test lib/stimmts/start-view.test.ts` — expect FAIL.
- [ ] **Step 3: Implement** the four components and wire `puzzle-game.tsx`.
- [ ] **Step 4: Run** `bun run test && bun run typecheck && bun run lint` — PASS.
- [ ] **Step 5: Check in the browser** (dev server, preview mode `?day=N`): "Tagesquiz", h1, three source pills linking to `…#page=…`; "Mehr Info" sets `aria-expanded="true"` and shows "Das Dokument", "Zurück zu den Punkten" restores it; "Los geht’s" starts the game once; 375 × 667 and 320 × 568 with the puzzle that has the longest `yesMeans` and with Tankrabatt; "Los geht’s" visible with "Mehr Info" open and closed, last bullet not under the bar; keyboard through (i), source pills, "Mehr Info", "Los geht’s"; VoiceOver reads the h1 first; desktop 1200 px swaps sides.
- [ ] **Step 6: Commit** `feat(stimmts): game-first start screen with sourced key points`.

### Task 6: Share-link banner

Board: "Start aus geteiltem Link" and its note.

**Files:**
- Create: `web/lib/stimmts/challenge.ts`, `web/lib/stimmts/challenge.test.ts`
- Modify: `web/components/stimmts/stimmts-game.tsx` (reads it from `search`), `web/components/stimmts/start-screen.tsx` (renders `banner`)

**Interfaces:**
- Consumes: `parseShareParams` (`share-image.ts`), `PUZZLE_COUNT`, `getGame`.
- Produces: `shareChallenge({ search: string, today: string, playedToday: boolean }): string | null` → the banner text or `null`.

- [ ] **Step 1: Write the failing tests:**

```ts
shareChallenge({ search: '?n=5&s=4&d=2026-11-19', today: '2026-11-19', playedToday: false }) // 'Schaffst du mehr als 4/5?'
shareChallenge({ search: '?n=5&s=5&d=2026-11-19', today: '2026-11-19', playedToday: false }) // 'Schaffst du auch 5/5?'
shareChallenge({ search: '?n=5&s=0&d=2026-11-19', today: '2026-11-19', playedToday: false }) // 'Schaffst du mehr als 0/5?'
shareChallenge({ search: '?n=5&s=4&d=2026-11-18', today: '2026-11-19', playedToday: false }) // null (other day)
shareChallenge({ search: '?n=5&s=9&d=2026-11-19', today: '2026-11-19', playedToday: false }) // null
shareChallenge({ search: '?n=5&s=4&d=2026-11-19', today: '2026-11-19', playedToday: true })  // null
shareChallenge({ search: '', today: '2026-11-19', playedToday: false })                    // null
```

- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** on top of `parseShareParams` (format `link`). **Step 4: Run** — PASS.
- [ ] **Step 5: Render** the banner above the logo row as `role="status"`, one line, as on the board. Check 320 px.
- [ ] **Step 6: Commit** `feat(stimmts): challenge the friend who opens a shared result`.

### Task 7: Share text and image

Boards: "Ablauf 5: Teilbild", "Baustein — Teilbild quadratisch", note "Lange Titel: 30 → 24 → 20 px, höchstens 3 Zeilen".

**Files:**
- Modify: `web/lib/stimmts/share.ts`, `share.test.ts`, `web/lib/stimmts/share-image.ts` (+ test), `web/components/stimmts/share-image.tsx`, `web/app/stimmts/share/route.tsx`, `web/components/stimmts/share-button.tsx`

**Interfaces:**
- Produces:
  - `buildShareText({ puzzleNumber, score, title, url })` →
    ```
    Stimmt's? #1 · 4/5 🟩🟩🟩🟩⬜

    Tankrabatt für Benzin und Diesel: Wie haben die Fraktionen abgestimmt? Ich hatte 4 von 5. Schaffst du mehr?
    https://wahl.chat/stimmts?n=1&s=4&d=2026-11-15
    ```
    At 5/5 the last sentence is "Schaffst du das auch?".
  - `shareTitleSize(title: string): 30 | 24 | 20` — the largest size whose layout fits in 3 lines at the image's text width.
  - The image reads the title from the puzzle by number (`n`) on the server; it is never a URL parameter.

The rule "the image never shows the title" is lifted: the title is public on the start screen and says nothing about the answers. Per-party ✓/✗ stays off the image and text.

- [ ] **Step 1: Write the failing tests** for the text above (4/5 and 5/5), for `shareTitleSize` with a 20-character, a 60-character and a 110-character title (30, 24, 20), and that a link image for `n=1` contains the Tankrabatt title while one without `n` shows the game's own card.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement**; use the wahl.chat logo from `web/public` (the same file as the site header's `Logo`), the vote title as main text, score secondary, `wahl.chat/stimmts` footer. **Step 4: Run** — PASS.
- [ ] **Step 5: Check** `/stimmts/share?f=square&n=1&s=4&d=2026-11-15` and the longest title in the browser; desktop "Ergebnis teilen" copies text + link.
- [ ] **Step 6: Commit** `feat(stimmts): share the vote title with the score`.

### Task 8: Result screen

Boards: "Ablauf 4: Ergebnis", "Baustein: Abstimmungskarte", "Stimmkarte (Feed-Stil)", "Ergebnis: Rückmeldung nach dem ersten Spiel".

**Files:**
- Create: `web/components/stimmts/vote-result-card.tsx`
- Modify: `web/components/stimmts/result.tsx`, `stimmkarte.tsx`, `outcome-card.tsx` (replaced by the vote card; delete if unused), `countdown.tsx`

**Interfaces:**
- Consumes: `OutcomeBadge` from `web/components/daily/vote-card.tsx`; `Hemicycle`/`SeatLegend` from `web/components/daily/hemicycle.tsx` where their props fit `PartyResult[]`, else the game's own `Hemicycle`; `feedDate` (Task 4).
- Produces: `VoteResultCard({ puzzle, onOpen }: { puzzle: Puzzle; onOpen: () => void })`.

Order, top to bottom: logo + "Nächstes Quiz in" + countdown (`role="timer"`); result card ("4 von 5 richtig", `feedDate(playDate)`, the five logos each with ✓/✗, `aria-label` "Richtig"/"Falsch"); "Ergebnis teilen"; the feedback card (unchanged behaviour); `VoteResultCard` ("● {topic} · Namentliche Abstimmung", "Angenommen"/"Abgelehnt" badge, title, hemicycle, "433 Ja · 127 Nein · 0 Enthalten · 67 Nicht beteiligt", "Quelle: Abgeordnetenwatch ↗"); then the chat card slot (Task 9); then the Stimmkarte in feed style with the "4/5 richtig" stamp beside the title (no overlap), the urn and the Wahlperiode as today.

- [ ] **Step 1: Write the failing test** that the vote card sums each answer over `puzzle.parties` (+ nothing for `unaffiliated`) and labels the four counts exactly as above, using the Tankrabatt fixture (433 / 127 / 0 / 67); put the sums in a pure `voteTotals(puzzle)` in `web/lib/stimmts/score.ts` if they are not there yet.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS.
- [ ] **Step 5: Check** in the browser: reload on the result keeps it (no replayed reveal), stamp and title do not overlap at 320 px, dark and light, reduced motion.
- [ ] **Step 6: Commit** `feat(stimmts): feed-style result with the vote card`.

### Task 9: Chat card (hidden)

Boards: "Chat: vor dem Fragen" (+ hell), "Chat: Antwort läuft", "Chat: beantwortet", "Chat: Folgefrage", "Chat: Desktop", "Baustein: Chat-Karte", and the note on 5/5.

**Files:**
- Create: `web/components/stimmts/chat-card.tsx`, `web/lib/stimmts/chat-chips.ts`, `web/lib/stimmts/chat-chips.test.ts`
- Modify: `web/lib/stimmts/chat-question.ts` (only if a helper is shared), `web/components/stimmts/result.tsx`

**Interfaces:**
- Consumes: `chatQuestion(puzzle, guesses)`, `SUBJECTS`-style party names.
- Produces: `STIMMTS_CHAT_ENABLED = false` (in `chat-chips.ts`); `chatChips(puzzle: Puzzle, guesses: Guesses): ChatChip[]` with `type ChatChip = { label: string; question: string }`.

Chips: first the wrong-guess chip, short ("Warum Nein, Grüne?"; the full question goes to the chat), then "Schon in Kraft?" and "Wie geht’s weiter?". At 5/5 the first chip is "Überraschendste Stimme?". Chips wrap; an asked chip disappears; the composer "Frage zu dieser Abstimmung …" sits under them; while an answer streams the send button shows a stop icon (`aria-label="Antwort stoppen"`); older turns collapse; "Im Chat weiter →" after an answer. Bill-status chips hand off to the general chat (Annika's RAG over government sources); no per-puzzle status data.

- [ ] **Step 1: Write the failing tests** for `chatChips`: one wrong party → its chip first with label ≤ 24 characters and a full question naming the party; 5/5 → first chip "Überraschendste Stimme?"; always exactly 3 chips.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** the rules and the card UI with a stub stream (no network) behind the flag. **Step 4: Run** — PASS.
- [ ] **Step 5: Check** with the flag set to `true` locally only: chips wrap at 320 px, focus order, live region announces the answer. Set it back to `false`.
- [ ] **Step 6: Commit** `feat(stimmts): chat card behind a switch until the general chat exists`.

### Task 10: Feed entry rules and presence script

Boards: "Baustein: Rätselkarte im Feed", notes "Glanz …" and "Nach dem Spiel …".

**Files:**
- Create: `web/lib/stimmts/feed-entry.ts`, `web/lib/stimmts/feed-entry.test.ts`, `web/lib/stimmts/presence.ts`, `web/lib/stimmts/presence.test.ts`
- Modify: `web/lib/firebase/firebase-server.ts` (`getStimmtsStatus`)

**Interfaces:**
- Consumes: `resolveLaunch`, `parseStimmtsStatus` (`status.ts`), `createSchedule`, `PUZZLES` (`content.ts`), `getTodaysPuzzle` (`schedule.ts`), `nextPuzzleAt`, `berlinDate`, `formatCountdown`, `STORAGE_KEY`.
- Produces:
  - `type FeedEntry = { kind: 'hidden' } | { kind: 'play'; number: number; shortName: string; endsAt: Date; isNew: boolean } | { kind: 'played'; number: number; score: number }`
  - `feedEntry({ status: StimmtsStatus; now: Date; progress: Progress; visitDays: number }): FeedEntry`
  - `NEW_FOR_DAYS = 14`, `NEW_FOR_VISITS = 3`
  - `recordFeedVisit(storage: StorageLike | null, today: string): number` (key `stimmts:feed-visits`, value `{"last":"YYYY-MM-DD","count":N}`, counts Berlin days, returns the count)
  - `type Presence = 'today' | 'before' | null`
  - `presenceOf(raw: string | null, today: string): Presence` — self-contained (no imports, no closures), so it can be inlined
  - `PRESENCE_SCRIPT: string` — sets `document.documentElement.dataset.stimmts` to the presence and `dataset.stimmtsFly = ''` when `sessionStorage['stimmts:just-played']` equals today's date; wrapped in `try {} catch {}`
  - `JUST_PLAYED_KEY = 'stimmts:just-played'`
  - `getStimmtsStatus(): Promise<StimmtsStatus>` (5-minute cache, tag `stimmts-status`, returns the off status on any error)

- [ ] **Step 1: Write the failing tests:**
  - `feedEntry` off / launch date in the future / past the last puzzle → `hidden`;
  - on, day 1 at `2026-11-15T22:59:59Z` (23:59:59 Berlin) → `play` with `shortName: 'Der Tankrabatt'` (fixture) and `endsAt` = next Berlin midnight; at `2026-11-15T23:00:01Z` → day 2's short name;
  - game finished yesterday → `play` today; finished today → `played` with its score;
  - `isNew` true on day 14 with 2 visit days, false on day 15, false with 3 visit days;
  - `getStimmtsStatus` with a reader that throws → the off status (inject the reader so the test needs no Firestore);
  - `recordFeedVisit` counts once per day, survives `null` storage (returns 1) and junk JSON (resets to 1);
  - `presenceOf(null, d)` → `null`; junk JSON → `null`; a game with `finishedOn === d` → `'today'`; only older finished games → `'before'`; unfinished games only → `null`;
  - `PRESENCE_SCRIPT` run with `new Function('document','localStorage','sessionStorage', PRESENCE_SCRIPT)` against fakes sets the attributes, and with a `localStorage` whose `getItem` throws leaves them unset and does not throw.
- [ ] **Step 2: Run** `bun test lib/stimmts/feed-entry.test.ts lib/stimmts/presence.test.ts` — FAIL.
- [ ] **Step 3: Implement.** `PRESENCE_SCRIPT` = `` `(${presenceOf.toString()})` `` applied to `localStorage.getItem(STORAGE_KEY)` and the Berlin date from `new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' })`.
- [ ] **Step 4: Run** — PASS, plus `bun run typecheck`.
- [ ] **Step 5: Commit** `feat(stimmts): rules for the feed entry and an early presence mark`.

### Task 11: Feed card on `/`

Boards: "Feed: Rätselkarte vor dem Spielen" (+ hell), "Feed: Desktop", "Baustein: Rätselkarte im Feed".

**Files:**
- Create: `web/components/daily/stimmts-feed-card.tsx`; `feedCardLabel` goes in `web/lib/stimmts/feed-entry.ts` with its tests in `feed-entry.test.ts`
- Modify: `web/app/(wide)/page.tsx` (fetch `getStimmtsStatus()` alongside the feed), `web/components/daily/daily-feed.tsx` (render the card between `FilterBar` and the day list), `web/app/layout.tsx` (inline `PRESENCE_SCRIPT` in `<head>`), `web/app/globals.css` (presence rules)

**Interfaces:**
- Consumes: `feedEntry`, `recordFeedVisit`, `PRESENCE_SCRIPT`, `getStimmtsStatus` (Task 10); `useStimmtsStatus`, `useProgress`; `CARD_SURFACE`, `CARD_LINK`, `FOCUS_RING`, `MUTED_TEXT` from `card-styles.ts`.
- Produces: `StimmtsFeedCard({ initialStatus }: { initialStatus: StimmtsStatus })`, root class `stimmts-feed-card`; `feedCardLabel(entry: FeedEntry, now: Date): string | null` → the link's accessible name, e.g. `"Stimmt’s?, neu: Heute: Der Tankrabatt. Jeden Tag ein neues Quiz. Noch 8 Stunden 41 Minuten. Los geht’s"`, `null` unless `kind === 'play'`.

Card (~100 px, whole card is one link to `/stimmts`, one tab stop):
- Row 1: seat logo + "Stimmt’s?" wordmark, outline "Neu" pill (only while `isNew`), right-aligned "noch 08:41:27" (muted, `tabular-nums`, `translate="no"`, `aria-label` "noch 8 Stunden 41 Minuten", updates each second).
- Row 2: "Heute: {shortName}" (15 px bold, at most 2 lines) over "Jeden Tag ein neues Quiz" (13 px muted); on the right the ink pill "Los geht’s →" with the shine sweep, only on the very first view (`localStorage['stimmts:shine-shown']`), off under reduced motion.
- Server render: when `initialStatus` is on, the full card with fixed-height slots; the short name and countdown slots render empty placeholders of the same size until mount. When off: nothing.
- CSS: `html[data-stimmts='today']:not([data-stimmts-fly]) .stimmts-feed-card { display: none }`.
- After mount the live `useStimmtsStatus` decides; `unreachable` keeps the server's decision.

- [ ] **Step 1: Write the failing tests** for `feedCardLabel`: a `play` entry with `isNew` at 15:18:33 Berlin → the example above; without `isNew` → no "neu"; `hidden` and `played` → `null`.
- [ ] **Step 2: Run** `bun test lib/stimmts/feed-entry.test.ts` — FAIL. **Step 3: Implement** the card and wire page, feed, layout script and CSS. **Step 4: Run** `bun run test && bun run typecheck && bun run lint` — PASS.
- [ ] **Step 5: Check** in the browser (emulator switch on, see `AGENTS.md`): one link to `/stimmts`, one tab stop; view-source shows the card without short name or countdown text; no shift when the page loads; 320 px with the longest short name; played today → card gone before first paint (throttle CPU, reload); switch off in the emulator → card disappears live; Firestore blocked → feed still renders; reduced motion → no shine.
- [ ] **Step 6: Commit** `feat(daily): Stimmt's? card above the Hot Topic`.

### Task 12: Header icon and fly-in

Boards: "Feed: nach dem Spielen, Symbol im Kopf" (+ hell), "Feed: Karte fliegt ins Symbol", note "Nach dem Spiel …".

**Files:**
- Create: `web/components/daily/stimmts-header-icon.tsx`, `web/components/daily/stimmts-fly-in.tsx`
- Modify: `web/components/daily/daily-header.tsx` (icon before the Chat link), `web/components/stimmts/puzzle-game.tsx` (set `JUST_PLAYED_KEY` when this page finishes the game), `web/components/daily/stimmts-feed-card.tsx` (played variant for the fly-in), `web/app/globals.css`

**Interfaces:**
- Consumes: `JUST_PLAYED_KEY`, presence attributes (Task 10); `StimmtsFeedCard` (Task 11).
- Produces: `StimmtsHeaderIcon()` — 44 × 44 link to `/stimmts`, 36 px round surface with the seat logo, ✓ badge when `data-stimmts='today'`; `aria-label` "Stimmt’s? – heute {n} von 5. Ergebnis und Quiz" when played today, else "Stimmt’s? – Ergebnis und Quiz". Hidden by CSS while `html` has no `data-stimmts`, and when the switch is off.

Fly-in, when `data-stimmts-fly` is set on arrival at `/`:
1. The card shows its played variant (logo · "Heute gespielt", "4/5" with ✓/✗ row).
2. FLIP from the card's rect to the icon's rect, ~600 ms, ease-out; the card's slot collapses with it.
3. The icon pulses once; the tooltip "Hier findest du dein Ergebnis" (`role="status"`) shows once ever (`localStorage['stimmts:icon-hint-shown']`) and fades after 4 s.
4. Clear `sessionStorage[JUST_PLAYED_KEY]` and remove `data-stimmts-fly`; also clear on `pageshow` with `persisted` (bfcache) so a back navigation never replays it.
Reduced motion: the card fades out (200 ms), no flight, no pulse; the tooltip still shows once.

- [ ] **Step 1: Write the failing test** for a pure `flipTransform(from: DOMRectLike, to: DOMRectLike): { x: number; y: number; scale: number }` (in `web/lib/stimmts/flip.ts`): card `{x:16,y:120,width:343,height:100}` to icon `{x:250,y:10,width:44,height:44}` → `scale` = 44/343, `x`/`y` move the card's centre onto the icon's centre.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** the helper, icon, fly-in and the flag write. **Step 4: Run** — PASS.
- [ ] **Step 5: Check** in the browser: finish a game, tap the News logo → card flies into the icon, tooltip once; reload → no flight; back button → no flight; reduced motion → fade; the icon is absent for a player who never finished a game and present on later days without the ✓.
- [ ] **Step 6: Commit** `feat(daily): Stimmt's? icon in the header after the first game`.

### Task 13: Whole-branch review

- [ ] **Step 1:** An independent reviewer checks `feat/stimmts` against this plan, the canvas and the Review Focus list; findings are fixed on their task's branch and merged again.
- [ ] **Step 2:** `cd web && bun run test && bun run lint && bun run typecheck`, then (dev server stopped) `bun run build` — all PASS.
- [ ] **Step 3:** Update `docs/stimmts/DESIGN.md` and the Stimmt's? section of `AGENTS.md` (feed card, header icon, presence script, `getStimmtsStatus` cache, `shortName`, sourced key points).
- [ ] **Step 4:** Update the PR wahl-chat/wahl-chat-app#210 description (no footer line). Push only on Miquel's go, to both remotes.

## Open questions for Miquel (before Task 5 / Task 8)

1. Result screen: keep the urn and the Wahlperiode under the vote card (this plan), or drop them as "Ablauf 4: Ergebnis" suggests?
2. Back side: ship it with the existing briefing text now, and write the headed sections ("Was ändert sich", "Was es kostet") for all 30 puzzles later?
