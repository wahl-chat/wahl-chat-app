import { STYLES, STYLE_MILESTONES, type StyleId } from './styles';

/** The bar runs to the last milestone. */
export const BAR_DAYS = STYLE_MILESTONES[STYLE_MILESTONES.length - 1];

function definition(id: StyleId) {
  const style = STYLES.find((entry) => entry.id === id);
  if (!style) {
    throw new Error(`Unknown style: ${id}`);
  }
  return style;
}

export function isLocked(id: StyleId, daysPlayed: number): boolean {
  return daysPlayed < definition(id).days;
}

/** The line under a thumb: when the style comes, or that it is always there. */
export function thumbSubline(id: StyleId, daysPlayed: number): string {
  const { days } = definition(id);
  if (days === 0) {
    return 'immer';
  }
  return isLocked(id, daysPlayed) ? `ab ${days} Tagen` : `${days} Tage`;
}

/** What a screen reader says for a thumb; the visual badges say the same. */
export function thumbLabel(
  id: StyleId,
  daysPlayed: number,
  isFresh: boolean,
): string {
  const { name, days } = definition(id);
  return [
    name,
    isLocked(id, daysPlayed) ? `ab ${days} Tagen` : null,
    isFresh ? 'neu' : null,
  ]
    .filter(Boolean)
    .join(', ');
}

/** Percent of the bar that is filled; more days than the bar holds fill it. */
export function barFill(daysPlayed: number): number {
  return (Math.min(Math.max(daysPlayed, 0), BAR_DAYS) / BAR_DAYS) * 100;
}

export function milestoneMarks(
  daysPlayed: number,
): { days: number; at: number; reached: boolean }[] {
  return STYLE_MILESTONES.map((days) => ({
    days,
    at: (days / BAR_DAYS) * 100,
    reached: daysPlayed >= days,
  }));
}

export function barLabel(daysPlayed: number): string {
  return `${daysPlayed} von ${BAR_DAYS} Tagen. Stile bei ${STYLE_MILESTONES.slice(0, -1).join(', ')} und ${BAR_DAYS} Tagen`;
}

/** Six thumbs (Festlich in season) would crowd five columns on a phone. */
export function gridColumns(thumbCount: number): number {
  return thumbCount > 5 ? 3 : 5;
}

/** Where an arrow key moves in the group, wrapping at both ends. */
export function nextIndex(
  current: number,
  key: string,
  count: number,
): number | null {
  switch (key) {
    case 'ArrowRight':
    case 'ArrowDown':
      return (current + 1) % count;
    case 'ArrowLeft':
    case 'ArrowUp':
      return (current - 1 + count) % count;
    case 'Home':
      return 0;
    case 'End':
      return count - 1;
    default:
      return null;
  }
}

export function styleName(id: StyleId): string {
  return definition(id).name;
}

export function styleButtonLabel(hasFresh: boolean): string {
  return hasFresh ? 'Stil ändern. Neuer Stil freigeschaltet' : 'Stil ändern';
}
