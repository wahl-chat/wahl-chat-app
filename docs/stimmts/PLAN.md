# Stimmt's? — daily vote-guessing puzzle

Working notes from the brainstorms of 2026-09-30. Nothing here is built yet.
This is a scratch document: trim it into a proper design note (or move it out
of the repo) before opening a PR.

## Why

- wahl.chat traffic follows the election calendar and drops between elections.
  A daily puzzle gives people a reason to come back in quiet periods.
- It moves the product towards "learn about politics regularly" without a
  large architectural change.
- It doubles as a funnel: every puzzle ends with a door into the chat.
- The result can be shared, so it also brings in new visitors.

## The game (decided)

One real Bundestag vote per day (**federal level**; Landtag editions are a
later idea). Working title: **Stimmt's?** ("Stimme" = vote, "stimmt's?" = is
that right?). Everyone gets the same puzzle on the same day: a day is defined
by midnight Europe/Berlin, and the puzzle is drawn from a pre-generated list.

### The flow

1. **Entry.** A card on the landing page opens today's puzzle.
2. **Briefing ("Antrag des Tages").** Title, date and a short neutral
   description of what was voted on. It must not reveal the result (see
   "Spoiler-free briefing").
3. **The hemicycle.** The parties appear as seats in party colours, in the
   order they sit in the Bundestag, left to right. One party at a time, the
   player answers **"Wie hat die Partei abgestimmt?"** with Ja / Nein /
   Enthaltung. One shot per party: no correcting, then on to the next seat,
   until the outermost right one.
4. **The reveal.** The player flips the seats over one by one and sees what
   each party really did (green = right, red = wrong, with the party's
   actual numbers). An "alle aufdecken" shortcut for the impatient.
5. **Score and share.** Score 0 to 5, the streak updates, a share button and a
   countdown to tomorrow's puzzle.
6. **"Mehr erfahren" (big button).** The reasons each party gave, taken from
   the plenary debate, with sources.
7. **Ask more.** From there, a link into a wahl.chat conversation about this
   vote (see "Chat handoff").

Design decisions that follow from this flow:

- **No retries and no attempts counter.** It replaces the Wordle-style
  multiple attempts. Each answer is committed on tap and saved immediately, so
  refreshing the page cannot be used to change an answer.
- **No difficulty levels.**
- **Predictions only.** The question is what the party did, never what the
  player thinks. Do not ask for the user's own position: that would be
  political-opinion data (see Constraints).
- **Streak = days played**, not days won, so a bad score never breaks it.
  Tiles are labelled and iconised, not colour-only, and animation respects
  reduced-motion settings.
- The whole loop should take 60 to 90 seconds. The reasons are a separate,
  optional step so the core loop stays short.
- Plan for roughly five seats, one per Bundestag faction (CDU/CSU as a single
  tile). The set comes from the vote's own party list.

## Spoiler-free briefing

The official text of a vote usually gives the answer away. Example from the
first candidate (Tankrabatt, 25 Sept 2026): "hat zugestimmt", the vote tally
(434 Ja, 128 Nein, keine Enthaltung), and "CDU/CSU und SPD begründen die
Maßnahme…" all reveal results or party positions. It is also a rider added to
an unrelated insurance-supervision law (VSAAG), so the formal title would
confuse players as well.

So each puzzle has two texts:

- **Before the guess:** a short, neutral "worum geht es?" that states the
  scope precisely (which articles, what the change would do) and says nothing
  about outcome, tally, or who argued for it.
- **After the reveal:** the full picture, with the official result and a link
  to the original source.

The neutral text is drafted with an LLM from the official text and approved by
a human. Also check who owns the source text and whether it may be reused
(Abgeordnetenwatch data vs the Bundestag's own pages): a link to the original
plus our own wording is the safe route.

## Choosing the votes

- **30 puzzles for the first month**, one per day, to test whether people
  care before investing more.
- Votes from **2026 onwards**, closer to today is better.
- We pick them ourselves, by importance. Write the selection criteria down
  *before* picking so the choice is defensible as neutral: public attention,
  spread across policy areas, and a mix of motions from government and
  opposition.
- **Mix predictable and surprising votes.** Many votes follow the
  government-versus-opposition line and are easy. The moments people share are
  the surprises (a party voting against its usual side, unexpected agreement
  between opposites). Aim for a healthy share of those.
- Supply caveat: per-party results exist for **roll-call votes**
  (namentliche Abstimmungen), which are only a subset of all votes. There may
  be fewer than 30 in 2026 so far; the window may have to reach back into late
  2025.

## Content rules for the reasons

The reveal is the riskiest part: an invented motive attributed to a real party
is a trust problem for a product whose value is being trustworthy.

1. Reasons come from the **plenary debate** on that motion (our corpus holds
   Bundestag speeches). Every reason cites a concrete source: a speech
   excerpt, a motion document, or a party statement.
2. Phrase it as attribution, not inference: "Die Linke begründete ihr Nein in
   der Debatte mit …", never "Die Linke lehnt ab, weil …".
3. Some votes have no debate. Then the card says so, instead of guessing.
4. A human reads all of them before they go live (30 votes x 5 parties is
   about 150 short texts, a few hours of work).
5. Same length and tone for every party.
6. Reasons are generated **offline in advance**, not at runtime. That is
   cheaper, safer and reviewable.

## The puzzle record (content contract)

Everything the game needs for one day, prepared and reviewed ahead of time:

- puzzle number, date it runs, review status
- source vote id, date of the vote, topic label (from the existing taxonomy)
- neutral title and spoiler-free briefing text
- official result: overall outcome and totals
- per party: seat position, the answer (Ja / Nein / Enthaltung), the counts,
  unity share
- per party: reason text, source link, short quote
- link to the original source
- the question used to open the chat

Stored as static content or a small Firestore collection with public read;
decide once the data check is done.

## Data check (do this first)

The game is only as good as its supply of clean votes. Before any UI, run a
throwaway check on the ~40 candidate votes:

- Do we have yes / no / abstain / no-show counts per party?
- Is each party unified enough to give one clear answer? Working rule: at
  least ~80% of the party's votes went one way. Otherwise the vote is
  ambiguous and is dropped.
- Can the motion be described in one neutral line?
- Does a source for each party's reasoning exist (a speech in that debate)?
- How many roll-call votes exist since January 2026?

Existing pieces to reuse: the vote data model (`VoteMeta` / `VoteResult` in
`ai-backend/src/ingestion/schemas.py`), the Abgeordnetenwatch client under
`ai-backend/src/ingestion/connectors/abgeordnetenwatch/`, its 53-label topic
taxonomy, and the existing voting-behaviour feature. Outcome: a table with a
verdict per vote and a go/no-go on whether 30 usable puzzles exist.

## Chat handoff

The chat should open on this vote with the question preloaded, for example
"Wie haben die Parteien beim Tankrabatt abgestimmt und warum?". Preferred
approach: prefill the question and let the normal retrieval find the vote and
the speeches, since both are already in the corpus. Injecting a long context
block is the alternative but easier to get wrong. Open points to verify:

- which chat context and which parties to open (a federal context, and
  whether it is available for chat between elections)
- reuse the mechanism the topic question cards already use to preload a
  question
- the Berlin / MV study contexts must not be the target

## Making it fun (keep brainstorming)

- Seats flipping one by one with a short delay for suspense; a small, tasteful
  celebration on a perfect score.
- Share text with the puzzle number, the topic and an emoji grid in seat
  order that shows only correctness, never the answers:

  ```
  Stimmt's? #47 · Tankrabatt · 4/5
  🟩🟥🟩🟩🟩
  wahl.chat/…
  ```

- A shareable image / link preview (OG image) carrying the hemicycle and the
  puzzle number. The share link must land on something playable without login.
- Crowd stat on the result ("62 % hatten alle richtig"): needs server-side
  counters, so later.
- A short "Wusstest du?" line on the reveal.

## Later ideas

- Other modes: "Welche Partei?" with progressive clues, civic trivia,
  coalition builder.
- An archive of past puzzles for catching up.
- Regional (Landtag) editions.
- Topic tags on puzzles as the first interest signal for personalization.
  Storing a per-user interest profile needs the explicit consent gate first.
- Reminders through the installed app / push.
- Upgrading the anonymous user to a login so streaks survive a cleared
  browser (the uid stays the same).

## Constraints

- **Neutrality**: facts with sources only; no loaded framing.
- **Privacy**: streak and puzzle state live on the device for now. Nothing
  political about the user is stored on the server. Predictions are not
  opinions; the player's own stance is never asked (political opinions are
  special-category data, see `AGENTS.md`).
- **Study**: keep the game out of the Berlin / MV chat contexts and respect
  the "only the study questionnaire asks anything" rule while the study is
  running (`useStudyRunning`).
- **Same puzzle for everyone**: puzzle N is a function of the Berlin date.
  Answers ship to the browser in v1 (acceptable for a casual game).

## Rough phases

1. Data check on the candidate votes.
2. Content: 30 approved puzzles (briefings, results, sourced reasons).
3. Minimal game: landing card, briefing, hemicycle answers, reveal, score,
   local streak, share button, chat handoff.
4. Polish for sharing: share image, countdown, animations.
5. After 30 days: look at return rate, streak lengths, shares and click-through
   into the chat; decide what to build next.
