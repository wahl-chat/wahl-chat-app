import { describe, expect, it } from 'bun:test';
import { FIXTURE_PUZZLES as PUZZLES } from './fixtures';
import { scorePuzzle } from './score';
import { buildClosingShareText, buildShareText } from './share';
import type { Guesses } from './types';

const puzzle = PUZZLES[0]; // real answers, in seating order: no, yes, no, yes, no
const RIGHT: Guesses = {
  linke: 'no',
  spd: 'yes',
  gruene: 'no',
  cdu: 'yes',
  afd: 'no',
};

const share = (guesses: Guesses) =>
  buildShareText({
    puzzleNumber: 47,
    score: scorePuzzle(puzzle, guesses),
    url: 'https://wahl.chat/stimmts',
  });

describe('buildShareText', () => {
  it('shows the puzzle number, the score and an invitation with the link', () => {
    const text = share({ ...RIGHT, spd: 'no', afd: 'yes' }); // 3 of 5 right
    expect(text).toBe(
      [
        "Stimmt's? #47 · 3/5 🟩🟩🟩⬜⬜",
        '',
        'Schlag meinen Score im neuen Spiel von wahl.chat: Wie haben die Parteien im Bundestag abgestimmt?',
        'https://wahl.chat/stimmts',
      ].join('\n'),
    );
  });

  it('fills the squares from the left, one per correct answer', () => {
    expect(share(RIGHT)).toContain('5/5 🟩🟩🟩🟩🟩');
    expect(
      share({ linke: 'yes', spd: 'no', gruene: 'yes', cdu: 'no', afd: 'yes' }),
    ).toContain('0/5 ⬜⬜⬜⬜⬜');
  });

  it('is identical for any two games with the same score, so it leaks nothing', () => {
    // 3 of 5 right, but different parties wrong each time.
    const wrongSpdAndAfd = share({ ...RIGHT, spd: 'no', afd: 'yes' });
    const wrongLinkeAndCdu = share({ ...RIGHT, linke: 'yes', cdu: 'no' });
    const wrongGrueneAndCdu = share({
      ...RIGHT,
      gruene: 'yes',
      cdu: 'abstain',
    });
    expect(wrongLinkeAndCdu).toBe(wrongSpdAndAfd);
    expect(wrongGrueneAndCdu).toBe(wrongSpdAndAfd);
  });

  it('never contains an answer or a party name', () => {
    const text = share(RIGHT);
    expect(text).not.toMatch(/\b(Ja|Nein|Enthaltung|yes|no|abstain)\b/);
    for (const party of ['Linke', 'SPD', 'Grünen', 'CDU', 'CSU', 'AfD']) {
      expect(text).not.toContain(party);
    }
  });
});

describe('buildClosingShareText', () => {
  it('sums up the whole run in numbers only', () => {
    expect(
      buildClosingShareText({
        summary: { played: 24, correct: 97, possible: 120 },
        days: 30,
        url: 'https://wahl.chat/stimmts',
      }),
    ).toBe(
      [
        "Stimmt's? · 24 von 30 Tagen gespielt · 97/120 richtig",
        '',
        'Das Rätsel von wahl.chat: Wie haben die Parteien im Bundestag abgestimmt?',
        'https://wahl.chat/stimmts',
      ].join('\n'),
    );
  });
});
