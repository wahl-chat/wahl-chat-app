import { describe, expect, it } from 'bun:test';
import { FIXTURE_PUZZLES as PUZZLES } from './fixtures';
import {
  AUTO_RESULT_DELAY_MS,
  allRevealed,
  autoResultDelay,
  chamberCenter,
  chamberStates,
  currentPartyIndex,
  gamePhase,
  selectParty,
} from './game-view';

const puzzle = PUZZLES[0];
const NONE = new Set<string>();
const TWO_ANSWERS = { linke: 'no', spd: 'yes' } as const;
const ALL_ANSWERS = {
  linke: 'no',
  spd: 'yes',
  gruene: 'abstain',
  cdu: 'yes',
  afd: 'no',
} as const;

describe('currentPartyIndex', () => {
  it('asks the parties in seating order', () => {
    expect(currentPartyIndex(puzzle, {})).toBe(0);
    expect(currentPartyIndex(puzzle, TWO_ANSWERS)).toBe(2);
    expect(currentPartyIndex(puzzle, ALL_ANSWERS)).toBe(-1);
  });
});

describe('gamePhase', () => {
  const at = (
    started: boolean,
    complete: boolean,
    finished: boolean,
    showResult = false,
  ) => gamePhase({ started, complete, finished, showResult });

  it('opens on the briefing', () => {
    expect(at(false, false, false)).toBe('briefing');
  });

  it('asks the parties once started', () => {
    expect(at(true, false, false)).toBe('answering');
  });

  it('reviews the tips once every party has one, until the reveal', () => {
    expect(at(true, true, false)).toBe('review');
    // A reload during the review resumes there.
    expect(at(false, true, false)).toBe('review');
  });

  it('reveals a finished game, then shows the result', () => {
    expect(at(true, true, true)).toBe('reveal');
    expect(at(false, true, true, true)).toBe('result');
  });
});

describe('chamberStates', () => {
  it('leaves the chamber neutral on the briefing', () => {
    const states = chamberStates(puzzle, 'briefing', {}, NONE);
    expect(Object.values(states).every((s) => s.mode === 'pending')).toBe(true);
  });

  it('shows tips as guesses, the asked party active, the rest dimmed', () => {
    const states = chamberStates(puzzle, 'answering', TWO_ANSWERS, NONE);
    expect(states.linke).toEqual({
      mode: 'guessed',
      guess: 'no',
      tappable: false,
    });
    expect(states.gruene).toEqual({ mode: 'active' });
    expect(states.afd).toEqual({ mode: 'pending', dim: true });
  });

  it('shows every tip on the review, none dimmed and none tappable', () => {
    const states = chamberStates(puzzle, 'review', ALL_ANSWERS, NONE);
    expect(states.linke).toEqual({
      mode: 'guessed',
      guess: 'no',
      tappable: false,
    });
    expect(states.afd).toEqual({
      mode: 'guessed',
      guess: 'no',
      tappable: false,
    });
    expect(Object.values(states).every((s) => s.mode === 'guessed')).toBe(true);
  });

  it('marks the party being edited as asked, while answering and on the review', () => {
    const answering = chamberStates(
      puzzle,
      'answering',
      TWO_ANSWERS,
      NONE,
      'linke',
    );
    expect(answering.linke).toEqual({ mode: 'active' });
    expect(answering.spd).toEqual({
      mode: 'guessed',
      guess: 'yes',
      tappable: false,
    });
    // The first party without a tip waits its turn like the rest.
    expect(answering.gruene).toEqual({ mode: 'pending', dim: true });

    const review = chamberStates(puzzle, 'review', ALL_ANSWERS, NONE, 'afd');
    expect(review.afd).toEqual({ mode: 'active' });
    expect(review.linke).toEqual({
      mode: 'guessed',
      guess: 'no',
      tappable: false,
    });
  });

  it('lets unrevealed parties be tapped on the reveal', () => {
    const states = chamberStates(
      puzzle,
      'reveal',
      ALL_ANSWERS,
      new Set(['linke']),
    );
    expect(states.linke).toEqual({ mode: 'revealed', tappable: true });
    expect(states.spd).toEqual({
      mode: 'guessed',
      guess: 'yes',
      tappable: true,
    });
  });
});

describe('chamberCenter', () => {
  it('counts the seats, then the parties, then the votes', () => {
    expect(chamberCenter(puzzle, 'briefing', {}, NONE)).toEqual({
      big: '630',
      small: 'Sitze',
    });
    expect(chamberCenter(puzzle, 'answering', TWO_ANSWERS, NONE)).toEqual({
      big: '3 / 5',
      small: 'Parteien',
    });
    expect(
      chamberCenter(puzzle, 'reveal', ALL_ANSWERS, new Set(['spd', 'linke'])),
    ).toEqual({ big: '116 : 54', small: 'Ja : Nein' });
  });

  it('counts all the parties on the review', () => {
    expect(chamberCenter(puzzle, 'review', ALL_ANSWERS, NONE)).toEqual({
      big: '5 / 5',
      small: 'Parteien',
    });
  });

  it('counts up to the party being edited', () => {
    expect(
      chamberCenter(puzzle, 'answering', TWO_ANSWERS, NONE, 'linke'),
    ).toEqual({ big: '1 / 5', small: 'Parteien' });
    expect(chamberCenter(puzzle, 'review', ALL_ANSWERS, NONE, 'cdu')).toEqual({
      big: '4 / 5',
      small: 'Parteien',
    });
  });

  it('names the outcome once every party is turned over', () => {
    const all = new Set(puzzle.parties.map((party) => party.partyId));
    expect(chamberCenter(puzzle, 'reveal', ALL_ANSWERS, all)).toEqual({
      big: '323 : 269',
      small: 'angenommen',
    });
  });
});

describe('selectParty', () => {
  const none = { revealed: new Set<string>(), open: null };

  it('turns a party over and opens its counts on the first tap', () => {
    const after = selectParty(none, 'spd');
    expect([...after.revealed]).toEqual(['spd']);
    expect(after.open).toBe('spd');
  });

  it('only ever adds to the turned-over parties', () => {
    const stale = new Set(['linke']);
    const after = selectParty({ revealed: stale, open: null }, 'spd');
    expect([...after.revealed].sort()).toEqual(['linke', 'spd']);
    const again = selectParty(
      { revealed: after.revealed, open: 'spd' },
      'linke',
    );
    expect([...again.revealed].sort()).toEqual(['linke', 'spd']);
  });

  it('opens and closes the counts on later taps, one party at a time', () => {
    const spdOpen = selectParty(none, 'spd');
    const closed = selectParty(spdOpen, 'spd');
    expect(closed.open).toBeNull();
    expect([...closed.revealed]).toEqual(['spd']);

    const linkeOpen = selectParty(spdOpen, 'linke');
    expect(linkeOpen.open).toBe('linke');
    expect([...linkeOpen.revealed].sort()).toEqual(['linke', 'spd']);
  });
});

describe('allRevealed', () => {
  const ids = puzzle.parties.map((party) => party.partyId);

  it('is false while a party is still face down', () => {
    expect(allRevealed(puzzle, new Set(ids.slice(0, -1)))).toBe(false);
    expect(allRevealed(puzzle, NONE)).toBe(false);
  });

  it('is true once every party is turned over, whatever else is in the set', () => {
    expect(allRevealed(puzzle, new Set(ids))).toBe(true);
    expect(allRevealed(puzzle, new Set([...ids, 'unknown']))).toBe(true);
  });
});

describe('autoResultDelay', () => {
  it('lets the finished tally be read, and is short without motion', () => {
    expect(AUTO_RESULT_DELAY_MS).toBe(1500);
    expect(autoResultDelay(false)).toBe(1500);
    expect(autoResultDelay(true)).toBe(300);
  });
});
