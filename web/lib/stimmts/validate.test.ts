import { describe, expect, it } from 'bun:test';
import { PUZZLES, SCHEDULE } from './content';
import puzzlesJson from './content/puzzles.json';
import fixturesJson from './fixtures/puzzles.json';
import { validatePuzzle, validateSchedule } from './validate';

// The parts of a puzzle the tests below tamper with, loosely typed on purpose:
// they feed deliberately broken data to the validator.
type RawPuzzle = {
  id: string;
  title: string;
  voteDate: string;
  source: { url: string };
  parties: { partyId: string; answer: string }[];
  unaffiliated?: unknown;
  document?: Record<string, unknown>;
};

// A fresh copy per test, so a test can break one field without touching the rest.
function firstPuzzle(): RawPuzzle {
  return structuredClone(fixturesJson[0]) as RawPuzzle;
}

describe('the shipped content', () => {
  it('loads and satisfies the puzzle contract', () => {
    expect(PUZZLES.length).toBe(puzzlesJson.length);
  });

  it('lists the five Bundestag factions in seating order, left to right', () => {
    for (const puzzle of PUZZLES) {
      expect(puzzle.parties.map((party) => party.partyId)).toEqual([
        'linke',
        'spd',
        'gruene',
        'cdu',
        'afd',
      ]);
    }
  });

  it('seats every member of the 21st Bundestag, Fraktion or not', () => {
    for (const puzzle of PUZZLES) {
      const members = puzzle.parties.reduce(
        (sum, party) =>
          sum + party.yes + party.no + party.abstain + party.noShow,
        puzzle.unaffiliated,
      );
      expect(members).toBe(630);
    }
  });

  it('schedules only puzzles that exist', () => {
    const ids = PUZZLES.map((puzzle) => puzzle.id);
    for (const id of SCHEDULE.puzzleIds) {
      expect(ids).toContain(id);
    }
  });
});

describe('validatePuzzle', () => {
  it('rejects an answer that does not match the vote counts', () => {
    const puzzle = firstPuzzle();
    puzzle.parties[1].answer = 'no'; // the SPD voted yes
    expect(() => validatePuzzle(puzzle)).toThrow('do not support');
  });

  it('rejects a party that was too divided for a single answer', () => {
    const puzzle = firstPuzzle();
    Object.assign(puzzle.parties[1], { yes: 60, no: 40, abstain: 0 });
    expect(() => validatePuzzle(puzzle)).toThrow('do not support');
  });

  it('rejects a party that cast no votes', () => {
    const puzzle = firstPuzzle();
    Object.assign(puzzle.parties[0], { yes: 0, no: 0, abstain: 0 });
    expect(() => validatePuzzle(puzzle)).toThrow('no votes were cast');
  });

  it('rejects a party listed twice', () => {
    const puzzle = firstPuzzle();
    puzzle.parties[1].partyId = puzzle.parties[0].partyId;
    expect(() => validatePuzzle(puzzle)).toThrow('appears twice');
  });

  it('rejects source links that are not http(s)', () => {
    const puzzle = firstPuzzle();
    puzzle.source.url = 'javascript:alert(1)';
    expect(() => validatePuzzle(puzzle)).toThrow('http(s) url');
  });

  it('rejects an impossible date', () => {
    const badDate = firstPuzzle();
    badDate.voteDate = '2026-13-45';
    expect(() => validatePuzzle(badDate)).toThrow('voteDate');
  });

  it('names the offending puzzle in the error', () => {
    const puzzle = firstPuzzle();
    puzzle.title = '';
    expect(() => validatePuzzle(puzzle)).toThrow(puzzle.id);
  });
});

describe('validatePuzzle: the bill document', () => {
  // The first fixture puzzle carries a verified Drucksache.
  function withDocument(): RawPuzzle & { document: Record<string, unknown> } {
    const puzzle = firstPuzzle();
    if (!puzzle.document) {
      throw new Error('the first fixture puzzle should have a document');
    }
    return puzzle as RawPuzzle & { document: Record<string, unknown> };
  }

  it('reads the Drucksache with the version voted on', () => {
    const puzzle = validatePuzzle(withDocument());
    expect(puzzle.document).toMatchObject({
      type: 'Gesetzentwurf',
      number: '21/6278',
      date: '2026-06-08',
      initiator: 'der Bundesregierung',
      votedIn: { number: '21/7009' },
    });
    expect(puzzle.unaffiliated).toBe(3);
  });

  it('leaves the document out when the puzzle has none', () => {
    const puzzle = firstPuzzle();
    puzzle.document = undefined;
    expect(validatePuzzle(puzzle).document).toBeUndefined();
  });

  it('accepts a Fraktion with the members who signed instead of an initiator', () => {
    const puzzle = withDocument();
    puzzle.document.initiator = undefined;
    puzzle.document.fraktion = 'der AfD';
    puzzle.document.members = ['Tobias Matthias Peterka', 'Fabian Jacobi'];
    expect(validatePuzzle(puzzle).document).toMatchObject({
      fraktion: 'der AfD',
      members: ['Tobias Matthias Peterka', 'Fabian Jacobi'],
    });
  });

  it('needs exactly one way of naming who submitted it', () => {
    const neither = withDocument();
    neither.document.initiator = undefined;
    expect(() => validatePuzzle(neither)).toThrow('either an "initiator"');

    const both = withDocument();
    both.document.fraktion = 'der AfD';
    both.document.members = ['Fabian Jacobi'];
    expect(() => validatePuzzle(both)).toThrow('either an "initiator"');

    const noMembers = withDocument();
    noMembers.document.initiator = undefined;
    noMembers.document.fraktion = 'der AfD';
    noMembers.document.members = [];
    expect(() => validatePuzzle(noMembers)).toThrow('"members"');
  });

  it('rejects a malformed Drucksache number, date or link', () => {
    const badNumber = withDocument();
    badNumber.document.number = '6278';
    expect(() => validatePuzzle(badNumber)).toThrow('Drucksache number');

    const badVotedIn = withDocument();
    badVotedIn.document.votedIn = {
      label: 'x',
      number: '21-7009',
      url: 'https://example.org',
    };
    expect(() => validatePuzzle(badVotedIn)).toThrow('Drucksache number');

    const badDate = withDocument();
    badDate.document.date = '08.06.2026';
    expect(() => validatePuzzle(badDate)).toThrow('"date"');

    const badUrl = withDocument();
    badUrl.document.url = 'javascript:alert(1)';
    expect(() => validatePuzzle(badUrl)).toThrow('http(s) url');
  });

  it('requires the count of members without a Fraktion', () => {
    const missing = firstPuzzle();
    missing.unaffiliated = undefined;
    expect(() => validatePuzzle(missing)).toThrow('"unaffiliated"');

    const negative = firstPuzzle();
    negative.unaffiliated = -1;
    expect(() => validatePuzzle(negative)).toThrow('"unaffiliated"');
  });
});

describe('validateSchedule', () => {
  const startDate = '2026-10-15';

  it('rejects a puzzle id that does not exist', () => {
    expect(() =>
      validateSchedule({ startDate, puzzleIds: ['no-such-puzzle'] }, PUZZLES),
    ).toThrow('unknown puzzle id');
  });

  it('rejects the same puzzle scheduled twice', () => {
    const id = PUZZLES[0].id;
    expect(() =>
      validateSchedule({ startDate, puzzleIds: [id, id] }, PUZZLES),
    ).toThrow('scheduled twice');
  });

  it('rejects an empty schedule', () => {
    expect(() =>
      validateSchedule({ startDate, puzzleIds: [] }, PUZZLES),
    ).toThrow('at least one');
  });
});
