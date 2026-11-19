# Stimmt's? feedback round — wave 1 implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the decided half of Robin's feedback (one-tap reveal, auto-move to the result, literal cast copy, chat-question logic) and produce the Kurzfassung drafts plus their PDF check, while the design track runs in Claude Design.

**Architecture:** UI changes stay inside the existing Stimmt's? components; new rules go in pure functions under `web/lib/stimmts/` tested with `bun test`, as the rest of the game does. Content work produces a review file, never puzzle data.

**Tech Stack:** Next.js 15 / React 19, TypeScript, Tailwind, `bun test`, `motion/react` (`useReducedMotion`).

**Spec:** `docs/superpowers/specs/2026-11-13-stimmts-feedback-round-design.md`

## Global Constraints

- Players predict; no copy may suggest they vote ("Stimme abgeben" is out).
- Party colours and vote dots are never changed.
- Chat questions are fixed neutral templates; the player's guesses never leave the device.
- `puzzles.json` is not touched in wave 1 (committed means approved).
- `PROGRESS_VERSION` and the stored progress shape are not changed.
- Accessibility: keyboard + screen reader, 320 px width, reduced motion all work.
- Code, identifiers and comments in English; user-facing copy in German. Comments explain why, never what changed.
- Verify with `cd web && bun run test`, `bun run lint`, `bun run typecheck`. Never `bun run build` while a dev server is running.

## Review Focus

1. "Auflösen" tapped twice quickly, or a row tapped mid-sequence → each party turns once, no stray timers, still one auto-move.
2. Leaving the reveal mid-sequence (unmount, new day at midnight) → no timer fires into a dead component; no auto-move.
3. "Abstimmung ansehen" from the result (votes-only view, everything already revealed) → never auto-moves back; keeps "Zurück zum Ergebnis".
4. Reduced motion → parties appear at once and the move to the result is near-immediate, without animation.
5. Chat question for a vote where all five Fraktionen voted alike, or for no guesses at all → a sensible, grammatical question, never an empty string or "undefined".

---

## Execution layout

| Task | Who | Where |
| --- | --- | --- |
| 1 Reveal + auto-move + cast copy | implementer + reviewer | worktree A, branch `stimmts/reveal-flow` |
| 2 Chat-question generator | implementer + reviewer | worktree B, branch `stimmts/chat-question` |
| 3 Kurzfassung drafts | content agent | main checkout, uncommitted file |
| 4 Kurzfassung PDF check | independent check agent (after 3) | main checkout, same file |
| D0–D4 Design track | Claude (this session) with Miquel | Claude Design |

Tasks 1, 2, 3 run in parallel. Claude merges A and B into `feat/stimmts` after each passes review; no push without Miquel's go. Wave 2 (approved designs) is planned as an addendum once the mockups are approved.

---

### Task 1: One-tap reveal, automatic move to the result, literal cast copy

**Files:**
- Modify: `web/components/stimmts/reveal.tsx`
- Modify: `web/components/stimmts/puzzle-game.tsx` (reveal timers ~lines 145–157, `Reveal` props ~227–241)
- Modify: `web/components/stimmts/result.tsx` (`CastHint` ~line 222, the card's `aria-label` in `stimmkarte.tsx` "In die Urne werfen")
- Modify: `web/lib/stimmts/game-view.ts`, Test: `web/lib/stimmts/game-view.test.ts`
- Modify: `docs/stimmts/DESIGN.md` (game step 4–5, state diagram "Reveal --> Result")

**Interfaces:**
- Produces: `export const AUTO_RESULT_DELAY_MS = 1500` and `export function autoResultDelay(reduceMotion: boolean): number` (300 when reduced) in `game-view.ts`; `export function allRevealed(puzzle: Puzzle, revealed: ReadonlySet<string>): boolean`.

- [ ] **Step 1: Failing tests** in `game-view.test.ts`:
  `allRevealed` is false with 4 of 5 parties, true with all 5, true with an extra unknown id plus all 5; `autoResultDelay(false) === 1500`, `autoResultDelay(true) === 300`.
- [ ] **Step 2:** `cd web && bun test lib/stimmts/game-view.test.ts` → FAIL (not exported).
- [ ] **Step 3: Implement** both functions in `game-view.ts`.
- [ ] **Step 4:** same command → PASS.
- [ ] **Step 5: "Auflösen" in `reveal.tsx`.** While not all revealed and `onRevealAll` is given, a `PillButton` labelled "Auflösen" sits between the "Deine Tipps" heading and the list (replace the hint line "Tippe auf eine Partei, um sie aufzudecken." with a smaller line under the button: "Oder tippe auf eine Partei."). Remove the ghost "Alle aufdecken" button. New prop `revealing: boolean`: while true the button is hidden (the sequence is running). "Zum Ergebnis" is removed; "Zurück zum Ergebnis" (no tips) stays.
- [ ] **Step 6: Sequence + auto-move in `puzzle-game.tsx`.** `revealAll` first clears any pending reveal timers, then queues; sets `revealing` true until the last party turns. Add an effect: when `phase === 'reveal'`, `!votesOnly`, and `allRevealed(puzzle, revealed)`, start a timer of `autoResultDelay(reduceMotion)` that does what `onShowResult` did (`setShowResult(true); setVotesOnly(false); goTop()`); clear it on cleanup. It must also fire when the last party is turned by row taps. `onShowResult` is passed only when `votesOnly`.
- [ ] **Step 7: Cast copy.** `CastHint` text becomes "Wirf deine Stimmkarte ein" (or a shorter literal variant that fits 320 px in one line; keep the pointer icon); the card's aria-label ends "In die Urne werfen" (unchanged meaning). No "Stimme abgeben".
- [ ] **Step 8: Docs.** Update `docs/stimmts/DESIGN.md`: step 4 (one "Auflösen" button; rows still tap), step 5 / diagram (Reveal → Result happens by itself after all parties are turned).
- [ ] **Step 9: Verify.** `cd web && bun run test && bun run lint && bun run typecheck` → all green. Run the game in the browser (dev server on a free port other than 3000, `?day=N` preview) and check Review Focus 1–4 by hand; screenshot the reveal at 320 px and desktop for the reviewer.
- [ ] **Step 10: Commit** on `stimmts/reveal-flow`: `feat(stimmts): one-tap reveal, automatic move to the result`.

---

### Task 2: Chat-question generator (logic only)

**Files:**
- Create: `web/lib/stimmts/chat-question.ts`
- Test: `web/lib/stimmts/chat-question.test.ts` (fixtures from `web/lib/stimmts/fixtures`; build ad-hoc puzzles by overriding `parties[].answer` where needed)

**Interfaces:**
- Produces:
  ```ts
  export type ChatQuestionKind = 'wrong-guess' | 'unusual-allies' | 'coalition-split' | 'general';
  export type ChatQuestion = { kind: ChatQuestionKind; text: string; partyIds: string[] };
  export function chatQuestion(puzzle: Puzzle, guesses: Guesses): ChatQuestion;
  ```
  Wave 2's chat CTA consumes `chatQuestion(puzzle, game.guesses).text`.

Rules, first match wins:
1. **wrong-guess** — among parties the player guessed wrong, pick the one whose actual answer is shared by the fewest other Fraktionen (most out of line); ties → seating order (`SEATING_ORDER`). Skipped when `guesses` is empty or all correct.
2. **unusual-allies** — `linke` and `afd` have the same answer and not all five Fraktionen voted alike.
3. **coalition-split** — `cdu` and `spd` have different answers.
4. **general** — about the vote itself, using `puzzle.title`.

German must be grammatical. A subject table in `chat-question.ts` (not `labels.ts`, whose names are for display): Die Linke, die SPD, die Grünen (**plural**: "haben"), die Union (CDU/CSU), die AfD. Abstaining reads "sich enthalten", not "mit Enthaltung gestimmt". Suggested templates (builder may polish, staying neutral):
- wrong-guess: "Warum hat die SPD mit Nein gestimmt?" / "Warum haben die Grünen mit Ja gestimmt?" / "Warum hat sich die AfD enthalten?"
- unusual-allies: "Warum haben Die Linke und die AfD hier gleich abgestimmt?"
- coalition-split: "Warum haben Union und SPD hier unterschiedlich abgestimmt?"
- general: "Worum ging es bei der Abstimmung „{title}“?"

- [ ] **Step 1: Failing tests**, one per rule plus: wrong-guess picks the out-of-line party when two are wrong; tie goes to seating order; Grünen use "haben"; abstain uses "sich … enthalten"; empty guesses skip rule 1; all five alike + empty guesses → `general` and text contains the title; `partyIds` lists the named parties; text never contains "undefined".
- [ ] **Step 2:** `cd web && bun test lib/stimmts/chat-question.test.ts` → FAIL.
- [ ] **Step 3: Implement** `chatQuestion` in `chat-question.ts`.
- [ ] **Step 4:** same command → PASS; then `bun run lint && bun run typecheck`.
- [ ] **Step 5: Coverage report:** a throwaway script (not committed) printing, for every scheduled puzzle and a few guess patterns (all right, all wrong, one wrong), the resulting question — included in the hand-back so Miquel can read the real wording.
- [ ] **Step 6: Commit** on `stimmts/chat-question`: `feat(stimmts): pick a chat question from the vote and the tips`.

---

### Task 3: Kurzfassung drafts (content)

**Files:** Create `docs/stimmts/kurzfassung-drafts.md` in the main checkout. **Do not commit. Do not touch `puzzles.json`.**

- [ ] **Step 1:** For every puzzle in `web/lib/stimmts/content/puzzles.json`, in schedule order (`schedule.json`) then spares, write a section: `## {n}. {title}` with `id`, then exactly 3 bullets.
- [ ] **Step 2: Rules for the bullets:** German; each ≤ 15 words; neutral (no evaluative adjectives, no party attributions beyond who submitted the bill); together they say what changes, for whom, and the key number or mechanism; nothing that hints at the result or at how a party voted; facts only from that puzzle's `briefing`, `yesMeans` and `document` fields, no outside knowledge. A bullet that cannot be written without outside facts says so in a `> Hinweis:` line instead.
- [ ] **Step 3: Self-check** each puzzle: word counts, no fact absent from the briefing; list any puzzle where 3 bullets felt too few under a final "Offene Punkte" section.

### Task 4: Kurzfassung PDF check (independent agent, after Task 3)

**Files:** Modify `docs/stimmts/kurzfassung-drafts.md` (adds a `### Prüfung` block under each puzzle; never edits bullets). PDFs go to the session scratchpad, not the repo.

- [ ] **Step 1:** For each puzzle with a `document`, download `document.url` (and `document.votedIn.url` if present) and read the relevant parts (title page, "A. Problem und Ziel", "B. Lösung", the changed articles for riders like the Tankrabatt).
- [ ] **Step 2:** Under `### Prüfung` write: **Abgleich** — "keine Konflikte" or each conflict as bullet/briefing claim vs. what the PDF says, with page; **Ratbarkeit** — "ausreichend" or "knapp" with one line on what's missing to make an informed guess at each Fraktion's vote (judge from the bullets alone, not the briefing). The puzzle without a `document` gets "kein Dokument — nicht geprüft".
- [ ] **Step 3:** Add a summary table at the top: puzzle, conflicts (count), Ratbarkeit.

---

### Design track (D0–D4, Claude with Miquel, in parallel)

- D0: Refresh the "Stimmt's? Design System" artifact from the current code.
- D1: #8 briefing card front (Gesetzentwurf, Kurzfassung, when, Ja means, "Mehr Details" dog-ear) + flip to the existing bill sheet.
- D2: #7 Stimmkarte lower half (topic in the current style).
- D3: #4 chat CTA position and how the pre-loaded question shows (after the cast).
- D4: #5 reward ladder 5/10/15/24 (days played; "nicht mehr erreichbar" state), themes, theme switch; settle the Christmas/season question.

Exit: Miquel approves the mockups → wave 2 addendum to this plan.
