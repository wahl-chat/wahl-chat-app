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

describe('a 30-day run from the launch date', () => {
  const thirty = Array.from({ length: 30 }, (_, i) => ({
    ...PUZZLES[i % PUZZLES.length],
    id: `puzzle-${i + 1}`,
  }));
  const run = (launchDate: string, iso: string) =>
    getTodaysPuzzle({
      schedule: { startDate: launchDate, puzzleIds: thirty.map((p) => p.id) },
      puzzles: thirty,
      now: new Date(iso),
    });

  it('makes the launch day day 1 and the 30th day after it the last', () => {
    expect(run('2026-11-15', '2026-11-14T12:00:00Z').status).toBe(
      'not-started',
    );
    expect(run('2026-11-15', '2026-11-15T12:00:00Z')).toMatchObject({
      number: 1,
    });
    expect(run('2026-11-15', '2026-12-14T12:00:00Z')).toMatchObject({
      number: 30,
    });
    expect(run('2026-11-15', '2026-12-15T12:00:00Z')).toEqual({
      status: 'finished',
    });
  });

  it('keeps counting days through the night the clocks go back', () => {
    // Berlin leaves summer time on 25 October 2026: that day is 25 hours long.
    expect(run('2026-10-20', '2026-10-25T22:30:00Z')).toMatchObject({
      number: 6,
    });
    expect(run('2026-10-20', '2026-10-25T23:00:00Z')).toMatchObject({
      number: 7,
    });
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
