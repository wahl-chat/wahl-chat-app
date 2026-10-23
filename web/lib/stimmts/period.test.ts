import { describe, expect, it } from 'bun:test';
import { PUZZLES } from './content';
import {
  type DayRecord,
  PERIOD_LENGTH,
  currentWahlperiode,
  dayRecords,
  encodePeriod,
} from './period';
import { EMPTY_PROGRESS, type Progress, recordAnswer } from './progress';
import type { Schedule, VoteAnswer } from './types';

const SCHEDULE: Schedule = {
  startDate: '2026-11-01',
  puzzleIds: PUZZLES.map((puzzle) => puzzle.id),
};

function play(
  progress: Progress,
  index: number,
  answer: VoteAnswer = 'no',
): Progress {
  const puzzle = PUZZLES[index];
  return puzzle.parties.reduce(
    (state, party) =>
      recordAnswer(state, puzzle, party.partyId, answer, '2026-11-01'),
    progress,
  );
}

/** A long run of records from a pattern: P played (score 4), x missed. */
function records(pattern: string): DayRecord[] {
  return [...pattern].map((mark, index) =>
    mark === 'P'
      ? {
          kind: 'played',
          number: index + 1,
          playDate: '2026-11-01',
          topic: 'Energie',
          score: 4,
        }
      : { kind: 'missed', number: index + 1, playDate: '2026-11-01' },
  );
}

describe('dayRecords', () => {
  it('turns finished games into played days with their score', () => {
    // Puzzle 1: Linke, Grüne and AfD voted no, SPD and CDU/CSU yes.
    const progress = play(EMPTY_PROGRESS, 0, 'no');
    const result = dayRecords({
      schedule: SCHEDULE,
      puzzles: PUZZLES,
      progress,
      throughNumber: 2,
    });
    expect(result).toEqual([
      {
        kind: 'played',
        number: 1,
        playDate: '2026-11-01',
        topic: 'Energie',
        score: 3,
      },
      { kind: 'missed', number: 2, playDate: '2026-11-02' },
    ]);
  });

  it('counts an unfinished game as not played', () => {
    const puzzle = PUZZLES[0];
    const progress = recordAnswer(
      EMPTY_PROGRESS,
      puzzle,
      'linke',
      'no',
      '2026-11-01',
    );
    const [day] = dayRecords({
      schedule: SCHEDULE,
      puzzles: PUZZLES,
      progress,
      throughNumber: 1,
    });
    expect(day.kind).toBe('missed');
  });

  it('stops at the end of the schedule and before the start', () => {
    const args = { schedule: SCHEDULE, puzzles: PUZZLES };
    const progress = EMPTY_PROGRESS;
    expect(dayRecords({ ...args, progress, throughNumber: 99 })).toHaveLength(
      PUZZLES.length,
    );
    expect(dayRecords({ ...args, progress, throughNumber: 0 })).toEqual([]);
  });
});

describe('currentWahlperiode', () => {
  it('keeps today in hand until its card is cast', () => {
    const before = currentWahlperiode(records('PxPP'), 4, false);
    expect(before.day).toBe(4);
    expect(before.days.map((day) => day.number)).toEqual([1, 2, 3]);
    expect(before.todayInHand).toBe(true);

    const after = currentWahlperiode(records('PxPP'), 4, true);
    expect(after.days.map((day) => day.number)).toEqual([1, 2, 3, 4]);
    expect(after.todayInHand).toBe(false);
  });

  it('cannot seat a card for a day that was not finished', () => {
    const period = currentWahlperiode(records('PPx'), 3, true);
    expect(period.days).toHaveLength(2);
    expect(period.todayInHand).toBe(true);
  });

  it('starts a new period after 30 days', () => {
    const period = currentWahlperiode(
      records('P'.repeat(PERIOD_LENGTH + 2)),
      PERIOD_LENGTH + 2,
      false,
    );
    expect(period.index).toBe(2);
    expect(period.day).toBe(2);
    expect(period.days.map((day) => day.number)).toEqual([PERIOD_LENGTH + 1]);
  });

  it('is complete only with all 30 days played', () => {
    const full = records('P'.repeat(PERIOD_LENGTH));
    expect(currentWahlperiode(full, PERIOD_LENGTH, true).complete).toBe(true);
    expect(currentWahlperiode(full, PERIOD_LENGTH, false).complete).toBe(false);

    const gap = records(`${'P'.repeat(PERIOD_LENGTH - 2)}xP`);
    expect(currentWahlperiode(gap, PERIOD_LENGTH, true).complete).toBe(false);
  });
});

describe('encodePeriod', () => {
  it('writes one character per day: the score, or x for a missed day', () => {
    const period = currentWahlperiode(records('PPxP'), 4, true);
    expect(encodePeriod(period.days)).toBe('44x4');
  });
});
