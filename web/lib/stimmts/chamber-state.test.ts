import { describe, expect, it } from 'bun:test';
import { chamberLabel, seatLook } from './chamber-state';
import { PUZZLES } from './content';
import { type Seat, layoutChamber } from './hemicycle';

const puzzle = PUZZLES[0];
const { seats } = layoutChamber(puzzle.parties, puzzle.unaffiliated);
const spdSeat = seats.find((seat) => seat.partyId === 'spd') as Seat;
const unaffiliatedSeat = seats.find((seat) => seat.partyId === null) as Seat;

describe('seatLook', () => {
  it('shows a guess as a ring and the truth as the real vote', () => {
    expect(seatLook(spdSeat, { mode: 'guessed', guess: 'no' })).toBe(
      'guess-no',
    );
    expect(seatLook(spdSeat, { mode: 'revealed' })).toBe('yes');
  });

  it('never changes the members without a Fraktion', () => {
    for (const state of [
      { mode: 'revealed' } as const,
      { mode: 'active' } as const,
    ]) {
      expect(seatLook(unaffiliatedSeat, state)).toBe('unaffiliated');
    }
  });
});

describe('chamberLabel', () => {
  it('reads out every party and the members without a Fraktion', () => {
    const label = chamberLabel(
      puzzle.parties,
      {
        linke: { mode: 'revealed' },
        spd: { mode: 'guessed', guess: 'yes' },
        gruene: { mode: 'active' },
      },
      puzzle.unaffiliated,
    );
    expect(label).toContain('630 Sitze');
    expect(label).toContain(
      'Die Linke: 0 Ja, 54 Nein, 0 Enthaltung, 10 abwesend',
    );
    expect(label).toContain('SPD: dein Tipp: Ja');
    expect(label).toContain('Bündnis 90/Die Grünen: wird gerade gefragt');
    expect(label).toContain('AfD: noch offen');
    expect(label).toContain('3 fraktionslose Abgeordnete');
  });
});
