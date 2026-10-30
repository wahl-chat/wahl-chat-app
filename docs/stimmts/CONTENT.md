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
   - `voteDate`, `outcome`, and per party the counts (`yes`, `no`, `abstain`,
     `noShow`) and the `answer`: copied from the vote's page.
   - `unaffiliated`: members without a Fraktion, so the chamber adds up to all
     630 seats.
   - `parties`: exactly `linke`, `spd`, `gruene`, `cdu`, `afd`, in that order.
   - `title`, `topic`, `briefing`, `yesMeans`: written by us (see the checklist).
   - `document` (optional): the Drucksache as printed on its cover. Leave it
     out if it cannot be verified; the briefing then uses the plain layout.
   - `source`: the vote's Abgeordnetenwatch page.
4. Add its id to `schedule.json` (or leave it out as a spare).
5. Run the checks and commit.

## Review checklist

Before a puzzle is committed, a person checks:

- [ ] The counts and answers match the vote's page, and every Fraktion's answer
      holds at least 80 percent of its votes cast (the validator enforces this).
- [ ] The title is neutral and does not hint at the result.
- [ ] The briefing explains what was voted on, in plain German, without the
      outcome, the tally, or who argued for or against it.
- [ ] `yesMeans` says in one sentence what a Ja vote meant. Take extra care
      with committee recommendations, where Ja can mean rejecting a motion.
- [ ] The Drucksache fields are copied exactly from the PDF, or left out.
- [ ] Across the schedule, topics and parties are mixed, and no run of days
      feels one-sided.

## Checks

```bash
cd web && bun test lib/stimmts
```

The tests load the real content through the validator and fail on a puzzle
that breaks the contract: an answer the counts do not support, parties missing
or out of order, seats that do not add up to all 630 members, unknown or
duplicate ids in the schedule.

To see a puzzle as players will, run `bun run dev` in `web/` and open
`http://localhost:3000/stimmts?day=N`. Locally, preview mode is always on, and
`?day=N` opens day N.

## Going live with a change

Content ships with the web app: a change reaches players with the next
deploy. If it has to land before a particular day's puzzle opens (at midnight
Berlin time), deploy it the day before.
