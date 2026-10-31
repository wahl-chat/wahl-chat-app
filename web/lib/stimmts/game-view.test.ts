import { describe, expect, it } from 'bun:test';
import { FIXTURE_PUZZLES as PUZZLES } from './fixtures';
import {
  chamberCenter,
  chamberStates,
  currentPartyIndex,
  selectParty,
  voteTotals,
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

  it('names the outcome once every party is turned over', () => {
    const all = new Set(puzzle.parties.map((party) => party.partyId));
    expect(chamberCenter(puzzle, 'reveal', ALL_ANSWERS, all)).toEqual({
      big: '323 : 269',
      small: 'angenommen',
    });
    expect(voteTotals(puzzle)).toEqual({ yes: 323, no: 269 });
  });
});

describe('selectParty', () => {
  const none = { revealed: new Set<string>(), open: null };

  it('turns a party over and opens its counts on the first tap', () => {
    const after = selectParty(none, 'spd');
    expect([...after.revealed]).toEqual(['spd']);
    expect(after.open).toBe('spd');
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
