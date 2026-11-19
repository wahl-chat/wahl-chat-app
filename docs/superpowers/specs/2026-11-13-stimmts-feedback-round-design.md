# Stimmt's? — feedback round 1 (Robin, 2026-11-12)

## Intent

Robin (CEO) played the draft of Stimmt's? (PR wahl-chat/wahl-chat-app#210) and
gave feedback. This round makes the game easier to start, faster to finish,
gives players a reason to come back every day, and prepares the door into the
general chat. No launch date is set; nothing here is rushed for one.

Players are lazy readers: anything they must read before playing has to be
hand-fed and short.

## Goals

1. **Briefing a player understands at a glance** (#8): a short summary first,
   the official bill one tap away.
2. **One tap to see the result** (#1, #2, #3): one main "Auflösen" action, the
   game moves on by itself, a literal cast instruction.
3. **A visible reason to keep playing** (#5): theme rewards at 5 / 10 / 15 / 24
   days played.
4. **The chat door, ready for when the general chat exists** (#4): a CTA with
   a question written from this vote and this player's tips.
5. **A Stimmkarte whose lower half matches the rest of the style** (#7).

## Non-goals (this round)

- **Login / server-side progress** (#6). Planned for a later round, after
  rewards exist (rewards are what make progress worth protecting). This round
  only keeps the progress format sync-ready (see Constraints).
- Linking to the chat for real: the general chat does not exist yet.
- Changing the launch mechanics, the 30-day Wahlperiode, or the scoring.

## Anti-goals

- Anything that asks the player for their own political position, or wording
  that suggests they are voting ("Stimme abgeben"). They predict.
- Themes that change party colours or vote dots: those carry meaning.
- Chat questions that are loaded or non-neutral ("Warum hat die AfD
  schon wieder …").
- Committing unreviewed content: in this repo committed means approved
  (`docs/stimmts/CONTENT.md`).
- Losing what the bill sheet does today (official cover, sources, PDF link).

## Constraints

- Code is the source of truth for the look. The design-system artifact
  ("Stimmt's? Design System", claude.ai, 2026-10-24) is stale and is refreshed
  from code before mockups.
- Progress stays in `localStorage` (`wahlchat.stimmts.progress`, versioned,
  games keyed by puzzle id). **Sync-ready means:** reward tiers are *derived*
  from finished games (like the Wahlperiode in `period.ts`), never stored as
  their own flags; the only new stored value is the chosen theme. A future sync
  then merges the games map only.
- Accessibility bar of `docs/stimmts/DESIGN.md` holds: keyboard + screen
  reader, 320 px, reduced motion.
- Repo workflow (this round only, Miquel's call): agents may work in parallel
  in their own worktrees and commit there; Claude merges the branches into
  `feat/stimmts`. Pushing and the PR update still wait for Miquel's go. Miquel
  gets a short summary of what each agent did.
- Pilot only: no planning for a second Wahlperiode.

## Approaches considered (sequencing)

- **A. Design everything first, then one build wave.** Coherent, but the small,
  already-decided items wait on design they don't need.
- **B. Two tracks in parallel — chosen.** Decided items are built now while the
  design track mocks up the rest in Claude Design; a second build wave follows
  approved mockups. Costs two review/PR-update rounds.
- **C. Prototype straight in the app, no Claude Design.** Fastest, but against
  what Miquel and Robin asked for, and themes / chat CTA benefit most from
  comparing options visually.

## Decided

### Track 1 — build now

**#1 Auflösen.** During the reveal, one primary button ("Auflösen") sits
*above* "Deine Tipps". It turns every remaining party over one after another
(the existing `revealAll` sequence). Rows stay tappable for a party-by-party
reveal and for opening counts. The ghost "Alle aufdecken" below the list goes.

**#2 Dynamic flow.** When the last party has turned (by button or by taps), the
game moves to the result by itself after a short pause (~1.5 s; immediate-ish
under reduced motion), replacing "Zum Ergebnis". The result already repeats
each party's verdict, so nothing is lost. Looking back at a past day (no
tips) keeps its "Zurück zum Ergebnis" button — no auto-move there.

**#3 Cast copy.** "Tippe auf deine Stimmkarte" becomes a literal instruction
along the lines of "Wirf deine Stimmkarte in die Urne" (final wording: the
builder's call within the anti-goals; the button's aria-label follows).

**#4 Chat question generator (logic only, no UI).** A pure function in
`web/lib/stimmts/` that, from a puzzle and the player's guesses, returns the
single best question to pre-load into the chat, plus tests. Candidate rules,
highest priority first:
1. The party the player got wrong (if several, the most surprising — e.g. the
   one whose vote went against the majority): "Warum hat die SPD mit Nein
   gestimmt?"
2. Unusual allies: AfD and Die Linke voting the same.
3. Coalition partners (CDU/CSU and SPD) voting differently.
4. Fallback: a general question about the vote's topic/title.
Questions are fixed neutral templates filled with party names and vote
labels from `labels.ts`; no free text. Exact rule set and wording: builder's
call, reviewed by Miquel. The guesses never leave the device: the question
holds only facts about the vote.

**#8 Kurzfassung drafts.** For every puzzle in `puzzles.json` (all, spares
included), draft exactly 3 bullets, each ≤ ~15 words, neutral, derived only
from the existing reviewed `briefing` and the stored `document` fields — no
fetching or reading PDFs (that would add unreviewed facts). The puzzle without
a `document` uses its briefing alone. Written to a review file
(`docs/stimmts/kurzfassung-drafts.md`), **not** into `puzzles.json`, and not
committed until Miquel has reviewed it; approved bullets move into the data in
wave 2.

**Kurzfassung check (separate agent, after drafting).** For every puzzle with
a `document`, an independent agent reads the Drucksache PDF and checks that
the 3 bullets correctly represent it. It does not rewrite: it lists conflicts
(bullet vs. PDF, and briefing vs. PDF if it spots one) in the draft file for
Miquel to investigate. It also judges, per puzzle, whether the 3 bullets carry
enough to make an informed guess at each Fraktion's vote, and flags those that
don't.

### Track 2 — design (Claude Design, with Miquel)

0. Refresh the "Stimmt's? Design System" artifact from the current code.
1. **#8 Briefing card:** front = Gesetzentwurf label, "Kurzfassung" with 3
   bullets, when it was voted, what "Ja" means, "Mehr Details" with a dog-ear.
   Tapping flips the card; the back is the existing bill sheet unchanged
   (paragraph, cover, PDF link). "Was Ja bedeutet" stays visible on every
   screen, as today.
2. **#7 Stimmkarte lower half:** topic shown in the current style (e.g. a chip
   or icon) instead of the italic/dotted form field.
3. **#4 Chat CTA:** where it sits on the result (after the cast) and how the
   pre-loaded question is shown.
4. **#5 Reward tiers and themes:** what each of 5 / 10 / 15 / 24 unlocks, how
   the next tier is shown from day 1 (the goal must be visible, like Spelling
   Bee's rank ladder), how a player switches theme. **Counting (decided):** a
   tier counts days played (finished, as in `dayRecords`), never the score.
   No catching up: a player who misses 7+ days cannot reach 24, and the ladder
   says so plainly once that happens. Open within design: the
   24-tier Christmas theme only fits December — tie it to the season or make
   the 24 tier season-neutral (decided in the mockups with Miquel).

### Wave 2 — build approved designs

Briefing card + flip, Kurzfassung data field (type, validator, CONTENT.md
rule), Stimmkarte topic, chat CTA UI (hidden until the chat exists, behind a
constant), reward tiers (derived) + themes + theme choice in storage.

## Process

- Each implementation subagent gets an independent reviewer subagent that
  checks the code for bugs and that the issue is actually solved, including
  screenshots at 320 px and desktop for UI work.
- Miquel plays through it before Robin is told.
- At the end: summary of changes, PR #210 description updated (no footer line),
  commit commands suggested to Miquel.

## Left to the builder

- Exact pause length and animation timing for #2.
- Exact cast copy (#3) and chat-question wording (#4), within the anti-goals.
- Function and file names.
