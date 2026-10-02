import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import { scorePuzzle } from './score';
import { buildShareText } from './share';

const puzzle = PUZZLES[0]; // real answers, in seating order: no, yes, no, yes, no

const share = (guesses: Parameters<typeof scorePuzzle>[1]) =>
  buildShareText({
    puzzleNumber: 47,
    topic: puzzle.topic,
    score: scorePuzzle(puzzle, guesses),
    url: 'https://wahl.chat/stimmts',
  });

describe('buildShareText', () => {
  it('shows the puzzle number, topic, score and a grid in seating order', () => {
    const text = share({
      linke: 'no',
      spd: 'no', // wrong
      gruene: 'no',
      cdu: 'yes',
      afd: 'yes', // wrong
    });
    expect(text).toBe(
      [
        "Stimmt's? #47 · Energie · 3/5",
        '🟩🟥🟩🟩🟥',
        'https://wahl.chat/stimmts',
      ].join('\n'),
    );
  });

  it('marks a perfect game with only green squares', () => {
    const text = share({
      linke: 'no',
      spd: 'yes',
      gruene: 'no',
      cdu: 'yes',
      afd: 'no',
    });
    expect(text).toContain('5/5\n🟩🟩🟩🟩🟩\n');
  });

  it('never reveals the answers, only whether they were right', () => {
    const text = share({
      linke: 'yes',
      spd: 'no',
      gruene: 'yes',
      cdu: 'no',
      afd: 'yes',
    });
    expect(text).toContain('0/5\n🟥🟥🟥🟥🟥\n');
    for (const word of ['Ja', 'Nein', 'Enthaltung', 'yes', 'no', 'abstain']) {
      expect(text).not.toContain(word);
    }
  });
});
