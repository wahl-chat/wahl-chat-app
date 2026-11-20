import { describe, expect, it } from 'bun:test';
import { STIMMTS_CHAT_ENABLED, chatChips, stimmtsChatHref } from './chat-chips';
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

describe('chatChips', () => {
  it('stays switched off until the general chat is in develop', () => {
    expect(STIMMTS_CHAT_ENABLED).toBe(false);
  });

  it('gives each chip an id that does not change with the wording', () => {
    const wrong = chatChips(votedLike(['no', 'yes', 'no', 'yes', 'no']), {
      ...guessed(['no', 'yes', 'no', 'yes', 'no']),
      gruene: 'yes',
    });
    expect(wrong.map((chip) => chip.id)).toEqual([
      'why_party',
      'in_force',
      'next',
    ]);
    const right = chatChips(
      votedLike(['no', 'yes', 'no', 'yes', 'no']),
      guessed(['no', 'yes', 'no', 'yes', 'no']),
    );
    expect(right.map((chip) => chip.id)).toEqual([
      'surprise',
      'in_force',
      'next',
    ]);
  });

  it('puts a short chip for the wrong party first, with the full question behind it', () => {
    const puzzle = votedLike(['no', 'yes', 'no', 'yes', 'no']);
    const [first] = chatChips(puzzle, {
      ...guessed(['no', 'yes', 'no', 'yes', 'no']),
      gruene: 'yes',
    });
    expect(first.label).toBe('Warum Nein, Grüne?');
    expect(first.label.length).toBeLessThanOrEqual(24);
    expect(first.question).toBe('Warum haben die Grünen mit Nein gestimmt?');
  });

  it('keeps every wrong-guess label within 24 characters', () => {
    const answers: VoteAnswer[] = ['yes', 'no', 'abstain'];
    for (const [i, party] of base.parties.entries()) {
      for (const actual of answers) {
        const votes: VoteAnswer[] = base.parties.map(() => 'yes');
        votes[i] = actual;
        const guess: VoteAnswer = actual === 'no' ? 'yes' : 'no';
        const [first] = chatChips(votedLike(votes), {
          ...guessed(votes),
          [party.partyId]: guess,
        });
        expect(first.label.length).toBeLessThanOrEqual(24);
        // "Warum Nein, Grüne?" names the party the question asks about.
        const shortName = first.label.split(', ')[1].slice(0, -1);
        expect(first.question).toContain(shortName);
      }
    }
  });

  it('words an abstention in the short label', () => {
    const puzzle = votedLike(['no', 'no', 'no', 'no', 'abstain']);
    const [first] = chatChips(puzzle, {
      ...guessed(['no', 'no', 'no', 'no', 'abstain']),
      afd: 'no',
    });
    expect(first.label).toBe('Warum Enthaltung, AfD?');
    expect(first.question).toBe('Warum hat sich die AfD enthalten?');
  });

  it('asks for the most surprising vote at 5/5', () => {
    const puzzle = votedLike(['no', 'yes', 'no', 'yes', 'no']);
    const [first] = chatChips(
      puzzle,
      guessed(['no', 'yes', 'no', 'yes', 'no']),
    );
    expect(first.label).toBe('Überraschendste Stimme?');
    expect(first.question).toContain(puzzle.title);
  });

  it('always offers exactly three chips, the bill status last', () => {
    const puzzle = votedLike(['no', 'yes', 'no', 'yes', 'no']);
    for (const guesses of [
      guessed(['no', 'yes', 'no', 'yes', 'no']),
      guessed(['yes', 'no', 'yes', 'no', 'yes']),
      { ...guessed(['no', 'yes', 'no', 'yes', 'no']), spd: 'no' as const },
    ]) {
      const chips = chatChips(puzzle, guesses);
      expect(chips).toHaveLength(3);
      expect(chips.slice(1).map((chip) => chip.label)).toEqual([
        'Schon in Kraft?',
        'Wie geht’s weiter?',
      ]);
      for (const chip of chips.slice(1)) {
        expect(chip.question).toContain(puzzle.title);
      }
    }
  });
});

describe('stimmtsChatHref', () => {
  it('links to /chat with the question and the poll id', () => {
    const url = new URL(stimmtsChatHref(base, 'Warum?'), 'https://wahl.chat');
    expect(url.pathname).toBe('/chat');
    expect(url.searchParams.get('q')).toBe('Warum?');
    expect(url.searchParams.get('poll_id')).toBe(String(base.pollId));
  });

  it('trims the question', () => {
    const url = new URL(
      stimmtsChatHref(base, '  Warum?  \n'),
      'https://wahl.chat',
    );
    expect(url.searchParams.get('q')).toBe('Warum?');
  });

  it('has no party_id and no preset', () => {
    const url = new URL(stimmtsChatHref(base, 'Warum?'), 'https://wahl.chat');
    expect([...url.searchParams.keys()].sort()).toEqual(['poll_id', 'q']);
  });

  it('encodes umlauts and quotes', () => {
    const question = 'Warum „Nein“ & „Enthaltung“ bei Grünen?';
    const href = stimmtsChatHref(base, question);
    expect(href).not.toContain(' ');
    expect(href).not.toContain('&Enthaltung');
    expect(new URL(href, 'https://wahl.chat').searchParams.get('q')).toBe(
      question,
    );
  });
});
