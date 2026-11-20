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

/**
 * Where an arrow key moves in the group, wrapping at both ends. Disabled
 * entries are skipped, so focus never rests on a radio that cannot be checked
 * while the checked one sits elsewhere. Null when the key is not a move or
 * nothing else can be reached.
 */
export function nextIndex(
  current: number,
  key: string,
  count: number,
  isDisabled: (index: number) => boolean = () => false,
): number | null {
  let step: number;
  let from: number;
  switch (key) {
    case 'ArrowRight':
    case 'ArrowDown':
      step = 1;
      from = current;
      break;
    case 'ArrowLeft':
    case 'ArrowUp':
      step = -1;
      from = current;
      break;
    case 'Home':
      step = 1;
      from = -1;
      break;
    case 'End':
      step = -1;
      from = count;
      break;
    default:
      return null;
  }
  for (let taken = 1; taken <= count; taken++) {
    const index = (((from + step * taken) % count) + count) % count;
    if (!isDisabled(index)) {
      return index === current && (key === 'Home' || key === 'End')
        ? null
        : index;
    }
  }
  return null;
}

export type SheetState = {
  /** The pick, kept local until it is confirmed. */
  selected: StyleId;
  /** What was new when the sheet opened; the badges stay until it closes. */
  freshOnOpen: StyleId[];
};

/** Opening starts from the style in use and notes what is new. */
export function openSheet(chosen: StyleId, fresh: StyleId[]): SheetState {
  return { selected: chosen, freshOnOpen: fresh };
}

/** A locked style cannot be picked; the state stays as it is. */
export function selectStyle(
  state: SheetState,
  id: StyleId,
  unlocked: boolean,
): SheetState {
  return unlocked ? { ...state, selected: id } : state;
}

/** The style the primary button hands to the store. */
export function confirmedStyle(state: SheetState): StyleId {
  return state.selected;
}

export function styleName(id: StyleId): string {
  return definition(id).name;
}

export function styleButtonLabel(hasFresh: boolean): string {
  return hasFresh ? 'Stil ändern. Neuer Stil freigeschaltet' : 'Stil ändern';
}
