# Stimmt's? — daily vote-guessing puzzle

Working notes for the feature, kept up to date as decisions are made. This is a
scratch document: trim it into a proper design note (or move it out of the
repo) before opening a PR.

## Why

- wahl.chat traffic follows the election calendar and drops between elections.
  A daily puzzle gives people a reason to come back in quiet periods.
- It moves the product towards "learn about politics regularly" without a
  large architectural change.
- It doubles as a funnel: every puzzle ends with a door into the chat.
- The result can be shared, so it also brings in new visitors.

## The game

One real Bundestag roll-call vote per day (**federal level**). Working title:
**Stimmt's?** ("Stimme" = vote, "stimmt's?" = is that right?). Everyone gets
the same puzzle on the same day: a day is defined by midnight Europe/Berlin.

1. **Entry.** A card on the landing page opens today's puzzle.
2. **Briefing ("Antrag des Tages").** Title, date, a short neutral description
   of what was voted on, and what a "Ja" means. It must not reveal the result.
3. **The hemicycle.** The parties appear as seats in party colours, in the
   order they sit in the Bundestag, left to right (verify the order against a
   seating chart). One party at a time, the player answers **"Wie hat die
   Partei abgestimmt?"** with Ja / Nein / Enthaltung. One shot per party, no
   correcting, then on to the next seat.
4. **The reveal.** The player flips the seats one by one and sees what each
   party really did (green = right, red = wrong, with the real numbers). An
   "alle aufdecken" shortcut for the impatient.
5. **Score and share.** Score 0 to 5, the streak updates, a share button and a
   countdown to tomorrow's puzzle.
6. **"Mehr erfahren".** The reasons each party gave in the plenary debate,
   with sources.
7. **Ask more.** A link into a wahl.chat conversation about this vote.

## Decisions taken (all easy to change)

Taken by us while the product owner was unavailable. Everything here is kept
reversible on purpose; the ones marked "confirm" should be checked with him.

- Federal level only; five seats (CDU/CSU as one tile).
- One shot per seat, score 0 to 5, no difficulty levels, no attempts counter.
  Answers are committed on tap and saved immediately, so a refresh cannot
  change them.
- Streak = days played, not days won.
- Predictions only: never ask for the player's own position (political
  opinions are special-category data, see `AGENTS.md`).
- Puzzle content lives as **files in the repo**, not in a database. A separate
  **schedule** file says which puzzle runs on which day, so swapping,
  reordering or dropping a puzzle is a one-line edit.
- Every puzzle has a `review_status` (draft / approved). Production only serves
  approved puzzles; drafts can be previewed in development.
- 30-day pilot with 30 puzzles picked by us (criteria below). Confirm: the 30
  votes, the name, the tone, the launch.

## What the data check found

Run against the public Abgeordnetenwatch API (no key needed) for the 21st
Bundestag:

- **72 roll-call votes in the term, 33 since January 2026.** Enough for a
  pilot, with little slack. Some cluster (five votes on one day about the
  health-insurance reform, four about energy tax), so 2026 holds roughly 20
  distinct topics; the rest will come from 2025. New votes keep arriving.
- **Parties vote as blocs**: in all 33 votes every party was 92 to 100 percent
  on one side. The unity rule (see the puzzle contract) is a safety net that
  almost never fires.
- **Union and SPD voted identically in 33 of 33 votes** (coalition discipline).
  So there are effectively four free decisions per puzzle, and regular players
  will notice. The surprise lives in the opposition seats and in Enthaltung,
  so votes are picked for variety (see criteria). It is also a civics lesson
  worth stating on the reveal.
- **"Ja" does not always mean what it sounds like.** Many votes are on a
  committee's recommendation ("Ablehnung eines Antrags …"), where Ja means
  "reject the motion". Every puzzle needs an explicit "Ja bedeutet …" line, and
  the pilot prefers direct laws and motions.
- **The official description spoils the answer** ("hat zugestimmt", the tally,
  who argued for it) and is 1,100 to 4,200 characters of HTML. It needs a
  short neutral rewrite; it also links the original Bundestag documents.
- Data quirk: party labels can carry an invisible soft hyphen (the Greens).

## Data source: the votes already in Qdrant

Suggested by a colleague, and the right call for the vote facts.

What one stored vote holds (one chunk per vote): title, publish date,
`external_id` (the Abgeordnetenwatch poll id), the Abgeordnetenwatch page as
citation, the list of participating parties, per-party yes / no / abstain /
no-show counts and a derived stance, the overall outcome (angenommen /
abgelehnt), and a text made of the title, the topic labels and the description
with the HTML removed. CDU/CSU is stored under the slug `cdu`.

Why use it:

- **One source of truth.** The chat reads the same chunks, so the puzzle and
  the chat can never disagree about a vote.
- The party mapping, the soft-hyphen handling and the tallies are already done
  and tested.
- Scheduled ingestion keeps new votes coming with no extra work.
- The speeches used for the reasons are in Qdrant too.

What it lacks or costs:

- The links to the Bundestag documents are stripped from the stored text. Use
  the stored Abgeordnetenwatch page as the source link instead.
- Topic labels are inside the text, not a separate field.
- The stored stance is a coarse derived label; we compute Ja / Nein /
  Enthaltung and the unity share from the counts instead.
- **The local Qdrant has no votes or speeches** (only the few pledge points).
  Options: ingest just the current term's votes locally (about 72 polls, a few
  minutes, small embedding cost), and get speeches through a snapshot of the
  corpus (the sanctioned way of moving corpus data, see `AGENTS.md`). Ask the
  colleague who works on the data layer how she gets corpus data locally.
- Reading production Qdrant directly is not the plan: local work stays on local
  stores.

How it is used: an **offline export script** reads Qdrant and writes the puzzle
files. The game itself never talks to Qdrant. The public API data from the data
check serves as a cross-check that the stored tallies match.

## The puzzle contract

Everything the game needs for one day, prepared and reviewed ahead of time.
All puzzles live in one `puzzles.json` (a list, so the export script can
regenerate it and a swap is an in-place edit), plus one `schedule.json`. Both
are checked when loaded (`validate.ts`), and the tests fail if a file breaks
the contract.

- id, `review_status`, date of the vote, source vote id, topic label
- neutral title, spoiler-free briefing, "Ja bedeutet …" line
- overall outcome and totals
- per party: seat position, the answer (Ja / Nein / Enthaltung), the counts,
  unity share (a vote where a party is under ~80% on one side is dropped or
  handled separately)
- per party: reason text, source, short quote, or "keine Debatte gefunden"
- link to the source, and the question used to open the chat

Schedule: launch date plus the ordered list of puzzle ids. Puzzle number and
"today's puzzle" are derived from it and the Berlin date.

## Spoiler-free briefing

Each puzzle has two texts. **Before the guess:** what is being decided, the
scope in one or two sentences, and what Ja means, saying nothing about the
result, the tally or who argued for it. **After the reveal:** the full picture
with the official result and the link to the source. The neutral text is
drafted with an LLM from the stored description and approved by a human. Check
who owns the source text before quoting it; our own wording plus a link is the
safe route.

## Reasons: sourced or absent

The reveal is the riskiest part: an invented motive attributed to a real party
is a trust problem for a product whose value is being trustworthy.

1. Reasons come from the **plenary debate** on that vote, found in the speeches
   in Qdrant: filter by the vote's date and the party, rank by similarity to
   the vote's subject, then have a human confirm the speech is about that
   agenda item.
2. Every reason cites a concrete speech (speaker, protocol, page) with a short
   quote.
3. Phrase it as attribution, not inference: "Die Linke begründete ihr Nein in
   der Debatte mit …", never "Die Linke lehnt ab, weil …".
4. Some votes have no debate, or a party did not speak. Then the card says so.
5. A human reads all of them before they go live; same length and tone for
   every party.
6. Generated offline in advance, never at runtime.

The link between a vote and its debate is not stored anywhere, so this lookup
is the least certain part of the plan and is tested on a few votes first.

## Choosing the votes

Criteria, written down before picking so the choice can be defended as neutral:

- 21st Bundestag roll-call votes, 2026 first, reaching into 2025 as needed.
- At most one puzzle per topic cluster.
- Prefer direct laws and motions; avoid "Ablehnung von …" votes unless "Ja
  bedeutet …" can be stated in a clear sentence.
- Spread across policy areas (at least 8 distinct topic labels) and across
  motions from government and opposition.
- At least a third with a real surprise (a seat that breaks the expected
  pattern), and a mix of angenommen / abgelehnt.
- Sensitive topics are fine when framed neutrally; rotate so no run of
  puzzles feels one-sided.

## Chat handoff

Open the chat with a prefilled question such as "Wie haben die Parteien beim
Tankrabatt abgestimmt und warum?" and let normal retrieval find the vote and the
speeches; the corpus already contains both. To verify: which chat context and
which parties to open (a federal context, available between elections), reuse
the mechanism the topic question cards use, and never target the Berlin / MV
study contexts.

## Constraints

- **Neutrality**: facts with sources only; no loaded framing.
- **Privacy**: streak and puzzle state live on the device for now; nothing
  political about the user is stored on the server.
- **Study**: keep the game out of the Berlin / MV chat contexts and respect
  the "only the study questionnaire asks anything" rule while the study is
  running (`useStudyRunning`).
- **Same puzzle for everyone**: puzzle N is a function of the Berlin date.
  Answers ship to the browser (acceptable for a casual game).

## How we build it

The aim is an **end-to-end game as early as possible**, rough at first, then
real content, then polish. Every step is small enough to read in one sitting,
leaves the app working, and ends with a suggested commit point. The author
reviews each change in the editor and makes the commits.

**Phase 1: walking skeleton (three real puzzles, rough, playable end to end)**

1. Types for the puzzle contract, three hand-built puzzles and a schedule.
2. The rules as pure functions with unit tests: today's puzzle number (Berlin
   midnight), scoring, streak update, share text.
3. State and saving: answers saved on tap, resume mid-game, hydration-safe.
4. A hidden page `/stimmts` (linked from nowhere): briefing, seat-by-seat
   answers, reveal, score. Plain elements.
5. Share button (native share with clipboard fallback), countdown, streak.
6. Chat handoff with the prefilled question.

Milestone: someone can play three puzzles start to finish in development and
land in the chat.

**Phase 2: real content**

1. Local data: ingest the current term's votes into the local Qdrant; get
   speeches by snapshot.
2. Export script: Qdrant to draft puzzle files (facts only).
3. Briefings and "Ja bedeutet" lines drafted and approved.
4. Reasons: speech retrieval, attributed drafts, human review.
5. Fill the 30 puzzles, mark them approved, write the schedule.

**Phase 3: look and feel**

Hemicycle in SVG with party colours, seat-flip animation, accessibility
(labels, not colour only; reduced motion), share image / link preview.

**Phase 4: release**

Landing-page card, a kill switch modelled on the study one, analytics events
(started, finished, shared, learn-more clicked), launch checklist, and a plan
for judging the pilot (return rate, streak lengths, shares, click-through to
chat).

**Pull requests**, small and invisible until the last one: (A) steps 1 to 3 of
phase 1, (B) the hidden page and its polish, (C) content and export scripts,
(D) landing card and switch, which is the launch.

## Making it fun (keep brainstorming)

- Share text with puzzle number, topic and an emoji grid in seat order that
  shows only correctness:

  ```
  Stimmt's? #47 · Tankrabatt · 4/5
  🟩🟥🟩🟩🟩
  wahl.chat/…
  ```

- Seats flipping one by one; a small celebration on a perfect score.
- A short "Wusstest du?" line on the reveal.
- Crowd stat ("62 % hatten alle richtig") needs server-side counters, so later.
- Optional bonus question: "Wurde der Antrag angenommen?" or a numeric guess,
  if the fixed Union / SPD pairing makes the core game too easy.

## Later ideas

- Other modes: "Welche Partei?" with progressive clues, civic trivia,
  coalition builder. An archive of past puzzles. Landtag editions.
- Topic tags as the first interest signal for personalization (a per-user
  profile needs the explicit consent gate first).
- Reminders through the installed app; upgrading the anonymous user to a login
  so streaks survive a cleared browser (the uid stays the same).
- A weekly "Abstimmung der Woche" generated from new votes as they are ingested.
