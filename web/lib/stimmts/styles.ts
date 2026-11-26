export type StyleId =
  | 'standard'
  | 'papier'
  | 'kuppel'
  | 'nacht'
  | 'festlich'
  | 'gold';

export type StyleDefinition = {
  id: StyleId;
  name: string;
  /** Days played that unlock the style. */
  days: number;
  /** Berlin months (1-12) in which the style exists at all. */
  months?: readonly number[];
};

export const STYLES: readonly StyleDefinition[] = [
  { id: 'standard', name: 'Standard', days: 0 },
  { id: 'papier', name: 'Papier', days: 3 },
  { id: 'kuppel', name: 'Kuppel', days: 5 },
  { id: 'nacht', name: 'Nacht', days: 7 },
  { id: 'gold', name: 'Gold', days: 15 },
  { id: 'festlich', name: 'Festlich', days: 15, months: [12] },
];

/** Days played at which a new style is handed out. */
export const STYLE_MILESTONES = [3, 5, 7, 15] as const;

export function isStyleId(value: unknown): value is StyleId {
  return STYLES.some((style) => style.id === value);
}

function inSeason(style: StyleDefinition, berlinMonth: number): boolean {
  return !style.months || style.months.includes(berlinMonth);
}

/** The styles the sheet lists; Festlich only exists in December. */
export function visibleStyles(berlinMonth: number): StyleId[] {
  return STYLES.filter((style) => inSeason(style, berlinMonth)).map(
    (style) => style.id,
  );
}

export function unlockedStyles(
  daysPlayed: number,
  berlinMonth: number,
): StyleId[] {
  return STYLES.filter(
    (style) => inSeason(style, berlinMonth) && daysPlayed >= style.days,
  ).map((style) => style.id);
}

/**
 * The saved choice is untrusted (storage can be edited) and can go stale (a
 * seasonal style outlives its month), so it only counts while it is unlocked.
 */
export function effectiveStyle(
  chosen: unknown,
  daysPlayed: number,
  berlinMonth: number,
): StyleId {
  if (!isStyleId(chosen)) {
    return 'standard';
  }
  return unlockedStyles(daysPlayed, berlinMonth).includes(chosen)
    ? chosen
    : 'standard';
}

/** Unlocked styles the player has not looked at yet. Standard is never new. */
export function freshStyles(
  unlocked: readonly StyleId[],
  seen: readonly StyleId[],
): StyleId[] {
  return unlocked.filter((id) => id !== 'standard' && !seen.includes(id));
}
