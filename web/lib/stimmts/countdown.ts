/** Milliseconds as HH:MM:SS, never below zero (it can be 25 hours on one day a year). */
export function formatCountdown(milliseconds: number): string {
  // Rounded up, so the last second still reads 00:00:01 and not 00:00:00.
  const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds]
    .map((part) => String(part).padStart(2, '0'))
    .join(':');
}
