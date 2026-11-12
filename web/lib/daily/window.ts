/** Days per load: the first visit and every "Ältere Tage anzeigen". */
export const FEED_WINDOW_DAYS = 14;

export function shiftDay(isoDay: string, days: number): string {
  const date = new Date(`${isoDay}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** First day of the slice that ends on `anchor`, an edition's date. */
export function pageStart(
  anchor: string,
  windowDays: number = FEED_WINDOW_DAYS,
): string {
  return shiftDay(anchor, -(windowDays - 1));
}

// Item keys (`bundestag_2026-07-10_v123`, `bundestag_2026-07-10_d90-top17`)
// start with their edition's id.
const EDITION_OF_KEY =
  /^((?:bundestag|landtag_st|landtag_bw)_\d{4}-\d{2}-\d{2})(?:_|$)/;

/** The edition (sitting day) an item key belongs to, or null. */
export function editionIdOf(itemKey: string): string | null {
  return EDITION_OF_KEY.exec(itemKey)?.[1] ?? null;
}
