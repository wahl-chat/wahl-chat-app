# Stimmt's? — daily vote-guessing puzzle

Working notes from the brainstorm of 2026-09-30. Nothing here is built yet.
This is a scratch document: trim it into a proper design note (or move it out
of the repo) before opening a PR.

## Why

- wahl.chat traffic follows the election calendar and drops between elections.
  A daily puzzle gives people a reason to come back in quiet periods.
- It moves the product towards "learn about politics regularly" without a
  large architectural change.
- It doubles as a funnel: every solved puzzle ends with a door into the chat.
- The result can be shared, so it also brings in new visitors.

## The game (decided)

- One real parliamentary vote per day, on **federal level (Bundestag)**.
  Regional (Landtag) editions are a later idea.
- The player sees a plain-language line about what was voted on, then sets
  each parliamentary party to **Ja / Nein / Enthaltung**.
- Feedback in the Wordle style: correct tiles turn green, wrong ones grey.
  A few attempts per puzzle (exact number still open, see below).
- After the puzzle: a reveal card with the real result and a short,
  neutral, sourced summary of each party's stated reasons, plus a
  **"Mehr erfahren"** button that opens a wahl.chat conversation with the
  question preloaded.
- **Everyone gets the same puzzle on the same day.** A day is defined by
  midnight Europe/Berlin. Puzzles are drawn from a pre-generated list.
- **Streak** and **puzzle number** (#47). No difficulty levels.
- **Countdown to tomorrow's puzzle** on the result screen.
- Lives on the landing page (a card that opens the puzzle).
- Working title: **Stimmt's?** ("Stimme" = vote, "stimmt's?" = is that right?).

## Content plan for the first month

- **30 puzzles**, one per day, so we can test whether people care before
  investing further.
- Votes from **2026 onwards**, the closer to today the better.
- We pick the votes ourselves, by importance. Write the selection criteria
  down *before* picking, so the choice can be defended as neutral:
  public attention, spread across policy areas, and a mix of motions from
  government and opposition parties.
- Reasons per party are drafted with an LLM but must be **grounded in a
  verifiable source** (see the rules below). A human reviews every one.
- If it works, optimise the pipeline after the first 30 days.

## Rules for the reason summaries

The reveal card is the riskiest part: an invented motive attributed to a real
party is a trust problem for a product whose value is being trustworthy.

1. Every reason cites a concrete source: an excerpt from a plenary speech in
   the debate on that motion, a motion document, or a party statement.
2. Phrase it as attribution, not inference: "Die Linke begründete ihr Nein in
   der Debatte mit …", never "Die Linke lehnt ab, weil …".
3. If no source exists for a party, say so on the card instead of guessing.
4. A human reads all of them before they go live (30 votes x 5 parties is
   about 150 short texts, a few hours of work).
5. Same length and tone for every party.

## Data check (do this first)

The game is only as good as its supply of clean votes. Before any UI, run a
throwaway check on the ~40 candidate votes:

- Per party, do we have the yes / no / abstain / no-show counts?
- Is each party unified enough to give one clear answer? Working rule: at
  least ~80% of the party's votes went one way, otherwise the vote is
  ambiguous and either dropped or handled separately.
- Can the motion be described in one neutral line?
- Does a source for each party's reasoning exist (speech, document)?

Existing pieces to reuse: the vote data model (`VoteMeta` / `VoteResult` in
`ai-backend/src/ingestion/schemas.py`: per-party counts, derived stance, and
the motion outcome), the Abgeordnetenwatch client under
`ai-backend/src/ingestion/connectors/abgeordnetenwatch/`, and its 53-label
topic taxonomy.

Outcome: a table of votes with a verdict per vote, and a go/no-go on whether
30 usable puzzles exist.

## Making it fun (still open, keep brainstorming)

- Tiles arranged as the Bundestag **hemicycle** in party colours; tiles flip
  one by one on submit for suspense.
- Share text with the puzzle number, attempts and an emoji grid that shows
  only correctness, never the answers (must not reveal political leanings):

  ```
  Stimmt's? #47 · 2/3
  🟩🟥🟩🟩🟥
  wahl.chat/…
  ```

- A shareable image / link preview (OG image) carrying the puzzle number.
- Crowd stat on the result ("62 % hatten alle richtig"): needs server-side
  counters, so later.
- Optional warm-up: "Wurde der Antrag angenommen?" before the party tiles.
- Friendly perfect-score wording; light animation, no anxiety mechanics
  around the streak.
- Undecided: number of attempts (three is friendly, two gives real failure)
  and whether the motion's outcome is shown up front.

## Later ideas

- Other modes: "Welche Partei?" with progressive clues, civic trivia,
  coalition builder.
- Regional (Landtag) editions.
- Topic tags on puzzles as the first interest signal for personalization.
  Storing a per-user interest profile needs the explicit consent gate first
  (political opinions are special-category data, see `AGENTS.md`).
- Reminders through the installed app / push, once there is something to
  come back for.
- Upgrading the anonymous user to a login so streaks survive a cleared
  browser (the uid stays the same).

## Constraints

- **Neutrality**: facts with sources only; no loaded framing.
- **Privacy**: the streak and the puzzle state live on the device for now.
  Nothing political about the user is stored on the server.
- **Study**: keep the puzzle out of the Berlin / MV chat contexts and respect
  the "only the study questionnaire asks anything" rule while the study is
  running (`useStudyRunning`).
- **Same puzzle for everyone**: puzzle N is a function of the Berlin date.
  Answers ship to the browser in v1 (acceptable for a casual game).
- The share link must land on something playable without a login.

## Rough phases

1. Data check on the candidate votes.
2. Content: 30 approved puzzles (votes, results, sourced reasons).
3. Minimal game: card on the landing page, puzzle screen, reveal card,
   local streak, share button, deep link into the chat.
4. Polish for sharing: hemicycle layout, share image, countdown.
5. After 30 days: look at return rate, streak lengths, shares, and click-through
   into the chat; decide what to build next.
