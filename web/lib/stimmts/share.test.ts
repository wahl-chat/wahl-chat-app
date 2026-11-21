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
    title: puzzle.title,
    url: 'https://wahl.chat/stimmts',
  });

const TANKRABATT = 'Tankrabatt für Benzin und Diesel';

describe('buildShareText', () => {
  it('names the vote and the score, and challenges the friend', () => {
    expect(
      buildShareText({
        puzzleNumber: 1,
        score: { correct: 4, total: 5 },
        title: TANKRABATT,
        url: 'https://wahl.chat/stimmts?n=1&s=4&d=2026-11-15',
      }),
    ).toBe(
      [
        "Stimmt's? #1 · 4/5 🟩🟩🟩🟩⬜",
        '',
        'Tankrabatt für Benzin und Diesel: Wie haben die Fraktionen abgestimmt? Ich hatte 4 von 5. Schaffst du mehr?',
        'https://wahl.chat/stimmts?n=1&s=4&d=2026-11-15',
      ].join('\n'),
    );
  });

  it('asks for a match, not more, after a perfect score', () => {
    expect(
      buildShareText({
        puzzleNumber: 1,
        score: { correct: 5, total: 5 },
        title: TANKRABATT,
        url: 'https://wahl.chat/stimmts?n=1&s=5&d=2026-11-15',
      }),
    ).toBe(
      [
        "Stimmt's? #1 · 5/5 🟩🟩🟩🟩🟩",
        '',
        'Tankrabatt für Benzin und Diesel: Wie haben die Fraktionen abgestimmt? Ich hatte 5 von 5. Schaffst du das auch?',
        'https://wahl.chat/stimmts?n=1&s=5&d=2026-11-15',
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
    // The title is the vote's own and public on the start screen; everything
    // around it must say nothing about how anyone voted.
    const text = share(RIGHT).replace(puzzle.title, '');
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
        'Das Quiz von wahl.chat: Wie haben die Parteien im Bundestag abgestimmt?',
        'https://wahl.chat/stimmts',
      ].join('\n'),
    );
  });
});
