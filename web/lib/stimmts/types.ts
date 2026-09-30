/** How a party voted, or how a player guesses it did. */
export type VoteAnswer = 'yes' | 'no' | 'abstain';

/** Production serves only approved puzzles; drafts are for development. */
export type ReviewStatus = 'draft' | 'approved';

export type PuzzleOutcome = 'accepted' | 'rejected';

export type SourceLink = {
  label: string;
  url: string;
};

export type PartyResult = {
  /** Canonical party slug, the same one the chat uses (e.g. 'gruene'). */
  partyId: string;
  /** The party as a whole: the option most of its members chose. */
  answer: VoteAnswer;
  yes: number;
  no: number;
  abstain: number;
  /** Members who did not vote; shown on the reveal, never part of the answer. */
  noShow: number;
};

/**
 * Why a party voted as it did, in its own words from the plenary debate.
 * A party without an entry has no sourced reason (yet); the reveal says so
 * instead of guessing.
 */
export type PartyReason = {
  partyId: string;
  text: string;
  quote: string;
  source: SourceLink;
};

export type Puzzle = {
  /** Stable slug; the schedule refers to puzzles by it. */
  id: string;
  reviewStatus: ReviewStatus;
  /** Day of the vote, ISO format (YYYY-MM-DD). */
  voteDate: string;
  topic: string;
  title: string;
  /** Shown before the guess, so it must not reveal the result. */
  briefing: string;
  /** Spells out what "Ja" means, which is not obvious for every vote. */
  yesMeans: string;
  outcome: PuzzleOutcome;
  /** In seating order, left to right. */
  parties: PartyResult[];
  reasons: PartyReason[];
  source: SourceLink;
  /** Opens the chat on this vote. */
  chatQuestion: string;
};

/** Which puzzle runs on which day: the puzzle number is the day count. */
export type Schedule = {
  /** Berlin date of puzzle #1 (YYYY-MM-DD). */
  startDate: string;
  puzzleIds: string[];
};
