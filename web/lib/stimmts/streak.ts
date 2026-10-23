import type { DayRecord } from './period';

export type Streak = {
  /** Days played in a row, up to today or, before today is played, yesterday. */
  current: number;
  /** The longest run of days played. */
  best: number;
};

/**
 * Worked out from the day records (see period.ts). The streak is days played,
 * not days won, so a bad score never breaks it; only a missed day does. An
 * unplayed today does not break it yet: the player still has until midnight.
 */
export function streakOf(records: DayRecord[], todayNumber: number): Streak {
  let best = 0;
  let run = 0;
  for (const record of records) {
    run = record.kind === 'played' ? run + 1 : 0;
    best = Math.max(best, run);
  }

  const played = (number: number) =>
    records.find((record) => record.number === number)?.kind === 'played';
  let day = played(todayNumber) ? todayNumber : todayNumber - 1;
  let current = 0;
  while (day >= 1 && played(day)) {
    current += 1;
    day -= 1;
  }
  return { current, best };
}
