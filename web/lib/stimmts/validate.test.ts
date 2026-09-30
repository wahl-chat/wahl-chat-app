import { describe, expect, it } from 'bun:test';
import { PUZZLES, SCHEDULE } from './content';
import puzzlesJson from './content/puzzles.json';
import { validatePuzzle, validateSchedule } from './validate';

// The parts of a puzzle the tests below tamper with, loosely typed on purpose:
// they feed deliberately broken data to the validator.
type RawPuzzle = {
  id: string;
  title: string;
  voteDate: string;
  reviewStatus: string;
  source: { url: string };
  parties: { partyId: string; answer: string }[];
  reasons: unknown[];
};

// A fresh copy per test, so a test can break one field without touching the rest.
function firstPuzzle(): RawPuzzle {
  return structuredClone(puzzlesJson[0]) as RawPuzzle;
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

  it('rejects a reason for a party that is not in the puzzle', () => {
    const puzzle = firstPuzzle();
    puzzle.reasons = [
      {
        partyId: 'fdp',
        text: 'x',
        quote: 'x',
        source: { label: 'x', url: 'https://example.org' },
      },
    ];
    expect(() => validatePuzzle(puzzle)).toThrow('not in the puzzle');
  });

  it('rejects an impossible date and an unknown review status', () => {
    const badDate = firstPuzzle();
    badDate.voteDate = '2026-13-45';
    expect(() => validatePuzzle(badDate)).toThrow('voteDate');

    const badStatus = firstPuzzle();
    badStatus.reviewStatus = 'maybe';
    expect(() => validatePuzzle(badStatus)).toThrow('reviewStatus');
  });

  it('names the offending puzzle in the error', () => {
    const puzzle = firstPuzzle();
    puzzle.title = '';
    expect(() => validatePuzzle(puzzle)).toThrow(puzzle.id);
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
