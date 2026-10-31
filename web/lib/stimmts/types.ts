/** How a party voted, or how a player guesses it did. */
export type VoteAnswer = 'yes' | 'no' | 'abstain';

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

/** The Drucksache version the Bundestag actually voted on, when it differs. */
export type VotedInDocument = {
  /** "Beschlussempfehlung des Ausschusses für Wirtschaft und Energie" */
  label: string;
  /** "21/7009" */
  number: string;
  url: string;
};

/**
 * Who submitted the bill, as the Drucksache prints it: either one line
 * ("der Bundesregierung") or a Fraktion with the members who signed it.
 */
export type DocumentSubmitter =
  | { initiator: string }
  | {
      fraktion: string;
      members: string[];
      /**
       * Everyone who signed, when only the first are named: the Bundestag's
       * DIP lists the first few signers by name, with the total.
       */
      memberCount?: number;
    };

/**
 * The bill behind the vote, copied exactly from its Drucksache. Only real
 * metadata goes here; a puzzle without a verified document shows the plain
 * briefing instead of the bill sheet.
 */
export type BillDocument = DocumentSubmitter & {
  /** "Gesetzentwurf", "Antrag", "Beschlussempfehlung und Bericht" */
  type: string;
  /** Wahlperiode and number, "21/6278". */
  number: string;
  /** The Drucksache's own date (YYYY-MM-DD), not the vote's. */
  date: string;
  /** The full official title, never shortened. */
  title: string;
  /** The PDF. */
  url: string;
  votedIn?: VotedInDocument;
};

export type Puzzle = {
  /** Stable slug; the schedule refers to puzzles by it. */
  id: string;
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
  /**
   * Members without a Fraktion. They are not part of the puzzle, but the
   * chamber draws them so it shows every seat.
   */
  unaffiliated: number;
  document?: BillDocument;
  source: SourceLink;
};

/** A player's answers so far, by party slug. */
export type Guesses = Record<string, VoteAnswer>;

/** Which puzzle runs on which day: the puzzle number is the day count. */
export type Schedule = {
  /** Berlin date of puzzle #1 (YYYY-MM-DD): the launch date from the switch. */
  startDate: string;
  puzzleIds: string[];
};
