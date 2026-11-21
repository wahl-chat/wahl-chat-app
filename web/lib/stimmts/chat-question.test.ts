import { describe, expect, it } from 'bun:test';
import { chatQuestion } from './chat-question';
import { FIXTURE_PUZZLES } from './fixtures';
import type { Guesses, Puzzle, VoteAnswer } from './types';

const base = FIXTURE_PUZZLES[0];

/** The fixture with the given answers, in seating order: linke, spd, gruene, cdu, afd. */
function votedLike(answers: VoteAnswer[]): Puzzle {
  return {
    ...base,
    parties: base.parties.map((party, i) => ({ ...party, answer: answers[i] })),
  };
}

function guessed(answers: VoteAnswer[]): Guesses {
  return Object.fromEntries(
    base.parties.map((party, i) => [party.partyId, answers[i]]),
  );
}

const noGuesses: Guesses = {};

describe('chatQuestion', () => {
  it('asks about the party the player got wrong', () => {
    const puzzle = votedLike(['no', 'yes', 'no', 'yes', 'no']);
    const q = chatQuestion(puzzle, {
      ...guessed(['no', 'yes', 'no', 'yes', 'no']),
      spd: 'no',
    });
    expect(q).toEqual({
      kind: 'wrong-guess',
      text: 'Warum hat die SPD mit Ja gestimmt?',
      partyIds: ['spd'],
    });
  });

  it('picks the party most out of line when two are wrong', () => {
    // spd (yes) shares its answer with cdu; gruene (abstain) is alone.
    const puzzle = votedLike(['no', 'yes', 'abstain', 'yes', 'no']);
    const q = chatQuestion(puzzle, {
      ...guessed(['no', 'yes', 'abstain', 'yes', 'no']),
      spd: 'no',
      gruene: 'yes',
    });
    expect(q.partyIds).toEqual(['gruene']);
  });

  it('breaks a tie in seating order', () => {
    // spd and afd are each one of a pair with the others; both wrong.
    const puzzle = votedLike(['no', 'yes', 'no', 'no', 'yes']);
    const q = chatQuestion(puzzle, {
      ...guessed(['no', 'yes', 'no', 'no', 'yes']),
      afd: 'no',
      spd: 'no',
    });
    expect(q.partyIds).toEqual(['spd']);
  });

  it('uses the plural verb for the Grünen', () => {
    const puzzle = votedLike(['no', 'no', 'yes', 'no', 'no']);
    const q = chatQuestion(puzzle, {
      ...guessed(['no', 'no', 'yes', 'no', 'no']),
      gruene: 'no',
    });
    expect(q.text).toBe('Warum haben die Grünen mit Ja gestimmt?');
  });

  it('words an abstention as sich enthalten', () => {
    const puzzle = votedLike(['no', 'no', 'no', 'no', 'abstain']);
    const q = chatQuestion(puzzle, {
      ...guessed(['no', 'no', 'no', 'no', 'abstain']),
      afd: 'no',
    });
    expect(q.text).toBe('Warum hat sich die AfD enthalten?');
    const plural = chatQuestion(
      votedLike(['no', 'no', 'abstain', 'no', 'no']),
      {
        ...guessed(['no', 'no', 'abstain', 'no', 'no']),
        gruene: 'yes',
      },
    );
    expect(plural.text).toBe('Warum haben sich die Grünen enthalten?');
  });

  it('skips the guess rule when nothing was guessed', () => {
    const puzzle = votedLike(['yes', 'no', 'no', 'no', 'yes']);
    expect(chatQuestion(puzzle, noGuesses).kind).toBe('unusual-allies');
  });

  it('skips the guess rule when every guess was right', () => {
    const answers: VoteAnswer[] = ['yes', 'no', 'no', 'no', 'yes'];
    const q = chatQuestion(votedLike(answers), guessed(answers));
    expect(q.kind).toBe('unusual-allies');
  });

  it('asks about Linke and AfD voting alike', () => {
    const q = chatQuestion(
      votedLike(['no', 'yes', 'yes', 'yes', 'no']),
      noGuesses,
    );
    expect(q).toEqual({
      kind: 'unusual-allies',
      text: 'Warum haben Die Linke und die AfD hier gleich abgestimmt?',
      partyIds: ['linke', 'afd'],
    });
  });

  it('asks about a split between Union and SPD', () => {
    const q = chatQuestion(
      votedLike(['no', 'yes', 'no', 'no', 'yes']),
      noGuesses,
    );
    expect(q).toEqual({
      kind: 'coalition-split',
      text: 'Warum haben Union und SPD hier unterschiedlich abgestimmt?',
      partyIds: ['cdu', 'spd'],
    });
  });

  it('falls back to the vote itself when all five voted alike', () => {
    const q = chatQuestion(
      votedLike(['yes', 'yes', 'yes', 'yes', 'yes']),
      noGuesses,
    );
    expect(q.kind).toBe('general');
    expect(q.text).toContain(base.title);
    expect(q.partyIds).toEqual([]);
  });

  it('does not call Linke and AfD unusual when the Union voted with them', () => {
    const q = chatQuestion(
      votedLike(['yes', 'no', 'no', 'yes', 'yes']),
      noGuesses,
    );
    expect(q.kind).toBe('coalition-split');
  });

  it('still asks about a wrong guess when all five voted alike', () => {
    const answers: VoteAnswer[] = ['yes', 'yes', 'yes', 'yes', 'yes'];
    const q = chatQuestion(votedLike(answers), {
      ...guessed(answers),
      cdu: 'no',
    });
    expect(q).toEqual({
      kind: 'wrong-guess',
      text: 'Warum hat die Union mit Ja gestimmt?',
      partyIds: ['cdu'],
    });
  });

  it('never prints undefined', () => {
    const answers: VoteAnswer[][] = [
      ['no', 'yes', 'no', 'yes', 'no'],
      ['abstain', 'abstain', 'abstain', 'abstain', 'abstain'],
      ['yes', 'no', 'abstain', 'yes', 'yes'],
    ];
    for (const a of answers) {
      for (const g of [noGuesses, guessed(['no', 'no', 'no', 'no', 'no'])]) {
        expect(chatQuestion(votedLike(a), g).text).not.toContain('undefined');
      }
    }
  });
});
