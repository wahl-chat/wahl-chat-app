import { describe, expect, it } from 'bun:test';
import { FIXTURE_PUZZLES as PUZZLES, TANKRABATT_PUZZLE } from './fixtures';
import { isComplete, scorePuzzle, voteCountLabels, voteTotals } from './score';
import type { Guesses } from './types';

// Seating order: linke, spd, gruene, cdu, afd. Real answers for this puzzle:
// no, yes, no, yes, no.
const puzzle = PUZZLES[0];

const allRight: Guesses = {
  linke: 'no',
  spd: 'yes',
  gruene: 'no',
  cdu: 'yes',
  afd: 'no',
};

describe('scorePuzzle', () => {
  it('gives full marks for all correct answers', () => {
    const score = scorePuzzle(puzzle, allRight);
    expect(score.correct).toBe(5);
    expect(score.total).toBe(5);
    expect(score.parties.every((party) => party.correct)).toBe(true);
  });

  it('counts every wrong answer, in seating order', () => {
    const score = scorePuzzle(puzzle, {
      ...allRight,
      spd: 'no',
      afd: 'abstain',
    });
    expect(score.correct).toBe(3);
    expect(score.parties.map((party) => party.correct)).toEqual([
      true,
      false,
      true,
      true,
      false,
    ]);
    expect(score.parties[1]).toEqual({
      partyId: 'spd',
      guess: 'no',
      actual: 'yes',
      correct: false,
    });
  });

  it('scores a party the player never answered as wrong', () => {
    const withoutAfd: Guesses = Object.fromEntries(
      Object.entries(allRight).filter(([partyId]) => partyId !== 'afd'),
    );
    const score = scorePuzzle(puzzle, withoutAfd);
    expect(score.correct).toBe(4);
    expect(score.parties[4]).toMatchObject({ guess: null, correct: false });
  });

  it('can score all wrong', () => {
    const allWrong: Guesses = {
      linke: 'yes',
      spd: 'no',
      gruene: 'yes',
      cdu: 'no',
      afd: 'yes',
    };
    expect(scorePuzzle(puzzle, allWrong).correct).toBe(0);
  });
});

describe('isComplete', () => {
  it('is true only once every party has an answer', () => {
    expect(isComplete(puzzle, {})).toBe(false);
    expect(isComplete(puzzle, { linke: 'no', spd: 'yes' })).toBe(false);
    expect(isComplete(puzzle, allRight)).toBe(true);
  });
});

describe('voteTotals', () => {
  it("sums every Fraktion's votes, leaving out the members without one", () => {
    expect(voteTotals(TANKRABATT_PUZZLE)).toEqual({
      yes: 433,
      no: 127,
      abstain: 0,
      noShow: 67,
    });
  });
});

describe('voteCountLabels', () => {
  it('names the four counts as the feed does, zeros included', () => {
    expect(voteCountLabels(voteTotals(TANKRABATT_PUZZLE))).toEqual([
      { vote: 'yes', label: '433 Ja' },
      { vote: 'no', label: '127 Nein' },
      { vote: 'abstain', label: '0 Enthalten' },
      { vote: 'noShow', label: '67 Nicht beteiligt' },
    ]);
  });
});
