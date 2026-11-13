import { addDays } from './berlin-time';
import { SEATING_ORDER } from './parties';
import { type Progress, getGame } from './progress';
import { scorePuzzle } from './score';
import type { Puzzle, Schedule } from './types';

/**
 * A Wahlperiode is 30 puzzles, the length of the pilot. The player's period
 * is drawn as the logo's own 30-seat chamber and fills one seat per day.
 */
export const PERIOD_LENGTH = 30;

type PlayedDay = {
  kind: 'played';
  /** The puzzle number, which is also the day of the schedule. */
  number: number;
  playDate: string;
  topic: string;
  score: number;
};

type MissedDay = {
  kind: 'missed';
  number: number;
  playDate: string;
};

export type DayRecord = PlayedDay | MissedDay;

type RecordsInput = {
  schedule: Schedule;
  puzzles: Puzzle[];
  progress: Progress;
  /** Today's puzzle number: records run from day 1 up to and including it. */
  throughNumber: number;
};

/**
 * One record per scheduled day, worked out from the saved games alone. A day
 * counts as played once its game is finished, cast or not; any other day is
 * missed, and stays so: there is no archive to catch up on.
 */
export function dayRecords({
  schedule,
  puzzles,
  progress,
  throughNumber,
}: RecordsInput): DayRecord[] {
  const byId = new Map(puzzles.map((puzzle) => [puzzle.id, puzzle]));
  const last = Math.min(throughNumber, schedule.puzzleIds.length);
  return Array.from({ length: Math.max(0, last) }, (_, index) => {
    const number = index + 1;
    const playDate = addDays(schedule.startDate, index);
    const puzzle = byId.get(schedule.puzzleIds[index]);
    const game = puzzle ? getGame(progress, puzzle.id) : null;
    if (!puzzle || !game || game.finishedOn === null) {
      return { kind: 'missed', number, playDate };
    }
    return {
      kind: 'played',
      number,
      playDate,
      topic: puzzle.topic,
      score: scorePuzzle(puzzle, game.guesses).correct,
    };
  });
}

export type Wahlperiode = {
  /** 1 for the first 30 days, 2 for the next 30, and so on. */
  index: number;
  /** Today's position in the period, 1 to 30. */
  day: number;
  /**
   * The seats filled so far: this period's days before today, then today
   * once its card is cast.
   */
  days: DayRecord[];
  /** Today's card has not gone into the urn yet; its seat waits, dashed. */
  todayInHand: boolean;
  /** Every one of the 30 days played: the period takes the logo's colours. */
  complete: boolean;
};

/**
 * The period that holds today. `records` must cover day 1 to today (see
 * dayRecords); `todayCast` says whether today's card is in the urn.
 */
export function currentWahlperiode(
  records: DayRecord[],
  todayNumber: number,
  todayCast: boolean,
): Wahlperiode {
  const index = Math.floor((todayNumber - 1) / PERIOD_LENGTH) + 1;
  const first = (index - 1) * PERIOD_LENGTH + 1;
  const before = records.filter(
    (record) => record.number >= first && record.number < todayNumber,
  );
  const today = records.find((record) => record.number === todayNumber);
  const seated = todayCast && today?.kind === 'played';
  const days = seated ? [...before, today] : before;
  return {
    index,
    day: todayNumber - first + 1,
    days,
    todayInHand: !seated,
    complete:
      days.length === PERIOD_LENGTH &&
      days.every((record) => record.kind === 'played'),
  };
}

/**
 * The score of each day in the period, one character per day: the digit for
 * a played day, `x` for a missed one. Small enough to ride in a share link,
 * so the share image needs nothing stored on a server.
 */
export function encodePeriod(days: DayRecord[]): string {
  return days
    .map((record) => (record.kind === 'played' ? String(record.score) : 'x'))
    .join('');
}

export type PeriodSummary = {
  played: number;
  correct: number;
  /** Five per played day: missed days count for nothing either way. */
  possible: number;
};

export function summarizePeriod(days: DayRecord[]): PeriodSummary {
  const played = days.filter((record) => record.kind === 'played');
  return {
    played: played.length,
    correct: played.reduce((sum, record) => sum + record.score, 0),
    possible: played.length * SEATING_ORDER.length,
  };
}
