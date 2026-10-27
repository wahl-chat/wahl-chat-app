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
