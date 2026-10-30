/**
 * The Fraktionen of the 21st Bundestag, in seating order from left to right.
 * Every puzzle lists exactly these, which is what lets the board, the score
 * and the share image count on five parties.
 */
export const SEATING_ORDER = ['linke', 'spd', 'gruene', 'cdu', 'afd'];

// Class names are spelled out in full so Tailwind finds them in the source.

const TILE_CLASSES: Record<string, string> = {
  linke: 'bg-party-linke',
  spd: 'bg-party-spd',
  gruene: 'bg-party-gruene',
  cdu: 'bg-party-cdu',
  afd: 'bg-party-afd',
};

const FILL_CLASSES: Record<string, string> = {
  linke: 'fill-party-linke',
  spd: 'fill-party-spd',
  gruene: 'fill-party-gruene',
  cdu: 'fill-party-cdu',
  afd: 'fill-party-afd',
};

// The app-wide Die Linke file is a 2160px square that is mostly empty, which
// leaves a speck on a small tile; the game uses a copy trimmed to the wordmark.
const LOGO_OVERRIDES: Record<string, string> = {
  linke: '/images/stimmts/linke.png',
};

/** The party's logo, drawn for its colour tile (never for the page ground). */
export function partyLogo(partyId: string): string {
  return LOGO_OVERRIDES[partyId] ?? `/images/${partyId}.png`;
}

/** Background of a party's logo tile; a neutral one for an unknown party. */
export function partyTileClass(partyId: string): string {
  return TILE_CLASSES[partyId] ?? 'bg-muted';
}

/** SVG fill for a party's band and tile on the hemicycle. */
export function partyFillClass(partyId: string): string {
  return FILL_CLASSES[partyId] ?? 'fill-muted';
}
