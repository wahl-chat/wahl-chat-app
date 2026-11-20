# Stimmt's? — changing the puzzles

How to swap, add or reorder puzzles, and what must never change once the game
is live. For how the game is built, see [DESIGN.md](DESIGN.md); for the on/off
switch, see the Stimmt's? section in [AGENTS.md](../../AGENTS.md).

## Where the puzzles live

Two files in `web/lib/stimmts/content/`:

- **`puzzles.json`** is the library: every reviewed puzzle, including spares
  that are not scheduled. Each one is identified by its `id`.
- **`schedule.json`** is the running order: a list of puzzle ids. The first id
  is day 1, the second day 2, and so on. The game lasts as many days as the
  list is long.

Day 1 is the launch date set in Firestore (`system_status/stimmts`), so day N
is the launch date plus N − 1 days, counted in Berlin time. The files contain
no dates at all.

**Committed means approved.** Everything in `puzzles.json` ships with the next
deploy, answers included, so only commit a puzzle once a person has reviewed
it (see the checklist below).

## The one rule after launch

**Only change days that have not been shown yet.** Today's day number is the
number of days since the launch date, plus one. Positions up to and including
today are history:

- Replacing a past day's id turns that day into a missed day for everyone who
  played it, and changes what their Wahlperiode and share images show.
- Moving an already shown puzzle to a later day makes it appear as already
  played on that day.
- Removing a shown puzzle from `puzzles.json` breaks the history the same way.

Everything after today can be swapped, reordered or removed freely. Before the
launch, everything can change.

## Swap a puzzle for a spare

1. Find a spare: a puzzle in `puzzles.json` whose `id` is not in
   `schedule.json`.
2. In `schedule.json`, replace the id you want to drop with the spare's id, at
   the same position.
3. Run the checks (below) and commit.

The dropped puzzle can stay in `puzzles.json` as a spare.

## Add a new vote

1. Pick a roll-call vote (namentliche Abstimmung) of the 21st Bundestag from
   [puzzle-selection.md](puzzle-selection.md), which lists every one with its
   voting pattern, or on
   [Abgeordnetenwatch](https://www.abgeordnetenwatch.de/bundestag/21/abstimmungen).
   The selection rules are in DESIGN.md under "Choosing the votes".
2. Add its poll id and the reason to `PICKS` in
   `ingestion/scripts/stimmts/selection.py`, and run the exporter from
   `ingestion/` (it needs `DIP_API_KEY` in `ingestion/.env` or
   `ai-backend/.env`):

   ```bash
   PYTHONPATH=src:../packages/wahlchat-common/src:scripts uv run python -m stimmts.export
   ```

   It writes a draft to `ingestion/scripts/stimmts/output/drafts.json`
   (never committed): the counts, answers and Drucksache filled in from the
   official records, the text fields empty, and `_review.notes` on anything to
   check. It also regenerates `puzzle-selection.md`. `--refresh` fetches
   everything again; `--no-dip` skips the Drucksachen and needs no key.
3. Copy the draft into `puzzles.json` without `_review`, write the text, and
   check the rest against the sources. The fields are defined and documented
   in `web/lib/stimmts/types.ts`:
   - `id`: a short slug, unique and never reused.
   - `pollId`: the vote's Abgeordnetenwatch poll id, a positive whole number,
     unique across puzzles (the validator refuses a puzzle without one, or a
     repeat). The exporter writes it. For a puzzle added by hand, it is the
     number in the poll's API URL, `abgeordnetenwatch.de/api/v2/polls/<id>`,
     and the key of the `PICKS` entry from step 2. The chat card
     anchors the general chat on it.
   - `voteDate`, `outcome`, and per party the counts (`yes`, `no`, `abstain`,
     `noShow`) and the `answer`: copied from the vote's page.
   - `unaffiliated`: members without a Fraktion, so the chamber adds up to all
     630 seats.
   - `parties`: exactly `linke`, `spd`, `gruene`, `cdu`, `afd`, in that order.
   - `title`, `topic`, `briefing`, `yesMeans`: written by us (see the checklist).
   - `shortName`: the feed card's name for the puzzle (see "Short name").
   - `keyPoints` (optional): three short bullets for the front of the
     briefing card, each with its source page (see below). The `briefing`
     moves into „Mehr Info“ (it expands on phones and is the card's back
     side on desktop).
   - `document` (optional): the Drucksache as printed on its cover. Leave it
     out if it cannot be verified; the briefing then uses the plain layout.
   - `source`: the vote's Abgeordnetenwatch page.
4. Add its id to `schedule.json` (or leave it out as a spare).
5. Run the checks and commit.

## Topics

The `topic` is a short German word, like `Energie` or `Migration`. The game
shows it with the feed's coloured topic dot. The feed has fewer, broader
topics, so `web/lib/stimmts/topic.ts` maps each word to one of them
(`Energie` to climate, `Verteidigung` to foreign policy, and so on).

Reuse a word that is already mapped where you can. A new word needs a new
line in that map, or the checks fail: without it, the puzzle would have no
dot.

## Key points

The briefing card shows three bullets before the long `briefing`. Players
read them first, often on a phone, so they must be quick to take in:

- Exactly three bullets, each at most 12 words.
- Plain language, one fact per bullet.
- Cover what changes, who it affects, and what it costs or demands.
- Plain text only: no `**` or other markup, since nothing renders it.
- No hint at the result: no outcome, no tally, no party positions.
- Every number or claim must be backed by the cited page.

Each key point is an object with `text` and `source`:

```json
{
  "text": "Tanken kann bis zu rund 17 Cent pro Liter billiger werden.",
  "source": { "document": "21/8157", "page": 428 }
}
```

`source.page` is the PDF page, the one `#page=N` opens, not the number
printed on the paper. The link is built from the Drucksache number
(`drucksache.ts`), so no URL is stored. When the puzzle has a `document`, a
source may only cite its `number` or its `votedIn.number`.

The validator checks the count, the length, no `*`, no spaces at the start
or end, a Drucksache number like `21/8157` and a whole page of 1 or more.

Words are counted at the spaces, so a dash between spaces counts:
`Oktober – Dezember` is three words.

## Short name

`shortName` completes "Heute: …" on the feed card:

- An article (Der, Die or Das) plus a noun or short noun phrase.
- At most 22 characters, spaces and article included.
- Everyday words, no verb.
- Neutral: no hint at how the vote went or where the parties stand.

## Review checklist

Before a puzzle is committed, a person checks:

- [ ] The counts and answers match the vote's page, and every Fraktion's answer
      holds at least 80 percent of its votes cast (the validator enforces this).
- [ ] The title and the short name are neutral and do not hint at the result.
- [ ] The briefing explains what was voted on, in plain German, without the
      outcome, the tally, or who argued for or against it.
- [ ] The key points, if any, follow the rules above and say nothing the
      briefing does not. Each cited page really shows its number or claim.
- [ ] `yesMeans` says in one sentence what a Ja vote meant. Take extra care
      with committee recommendations, where Ja can mean rejecting a motion.
- [ ] The Drucksache fields are copied exactly from the PDF, or left out.
      Compare them with the cover, not with DIP: DIP shortens committee
      names ("Sportausschuss" for "Ausschuss für Sport und Ehrenamt"), writes
      some Fraktionen differently ("DIE LINKE", "der AfD"), and flattens the
      cover's dashes (the exporter restores those).
- [ ] Across the schedule, topics and parties are mixed, and no run of days
      feels one-sided.

## Checks

```bash
cd web && bun test lib/stimmts
```

The tests load the real content through the validator and fail on a puzzle
that breaks the contract: an answer the counts do not support, parties missing
or out of order, seats that do not add up to all 630 members, a topic word
with no feed topic, key points that break the rules, unknown or duplicate ids
in the schedule.

To see a puzzle as players will, run `bun run dev` in `web/` and open
`http://localhost:3000/stimmts?day=N`. Locally, preview mode is always on, and
`?day=N` opens day N.

## Going live with a change

Content ships with the web app: a change reaches players with the next
deploy. If it has to land before a particular day's puzzle opens (at midnight
Berlin time), deploy it the day before.
