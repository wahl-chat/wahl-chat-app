import { describe, expect, it } from 'bun:test';
import { FIXTURE_PUZZLES as PUZZLES } from './fixtures';
import { getTodaysPuzzle, puzzleForDay } from './schedule';
import type { Schedule } from './types';

const schedule: Schedule = {
  startDate: '2026-10-15',
  puzzleIds: PUZZLES.map((puzzle) => puzzle.id),
};

const on = (iso: string) =>
  getTodaysPuzzle({ schedule, puzzles: PUZZLES, now: new Date(iso) });

describe('getTodaysPuzzle', () => {
  it('waits for the start date', () => {
    expect(on('2026-10-14T12:00:00Z')).toEqual({
      status: 'not-started',
      startsOn: '2026-10-15',
    });
  });

  it('serves puzzle #1 on the start date and the next one each day after', () => {
    const first = on('2026-10-15T12:00:00Z');
    expect(first).toMatchObject({ status: 'active', number: 1 });
    expect(on('2026-10-16T12:00:00Z')).toMatchObject({ number: 2 });
    expect(on('2026-10-17T12:00:00Z')).toMatchObject({ number: 3 });
    if (first.status === 'active') {
      expect(first.puzzle.id).toBe(schedule.puzzleIds[0]);
    }
  });

  it('switches puzzles at Berlin midnight, not at UTC midnight', () => {
    // 15 Oct 23:59:59 in Berlin is still puzzle 1; one second later it is 2.
    expect(on('2026-10-15T21:59:59Z')).toMatchObject({ number: 1 });
    expect(on('2026-10-15T22:00:00Z')).toMatchObject({ number: 2 });
  });

  it('runs out after the last scheduled puzzle', () => {
    expect(on('2026-10-18T12:00:00Z')).toEqual({ status: 'finished' });
  });
});

describe('puzzleForDay', () => {
  it('finds the puzzle that ran on a day', () => {
    expect(puzzleForDay({ schedule, puzzles: PUZZLES, number: 2 })?.id).toBe(
      PUZZLES[1].id,
    );
  });

  it('has nothing outside the schedule', () => {
    for (const number of [0, PUZZLES.length + 1]) {
      expect(puzzleForDay({ schedule, puzzles: PUZZLES, number })).toBeNull();
    }
  });
});
