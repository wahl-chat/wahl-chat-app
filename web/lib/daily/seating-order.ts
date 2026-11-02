/**
 * Left-to-right order of party blocks in the hemicycle, following the usual
 * German plenary seating. Parties not listed sit between the known ones and the
 * unaffiliated members, who always come last.
 */
const SEATING_ORDER = [
  'linke',
  'bsw',
  'spd',
  'gruene',
  'ssw',
  'fdp',
  'fw',
  'cdu',
  'csu',
  'afd',
];

const TRAILING = ['fraktionslos', 'fraktionslose', 'unbekannt'];

function rank(partyId: string): number {
  const known = SEATING_ORDER.indexOf(partyId);
  if (known !== -1) {
    return known;
  }
  const trailing = TRAILING.indexOf(partyId);
  if (trailing !== -1) {
    return SEATING_ORDER.length + 1 + trailing;
  }
  return SEATING_ORDER.length;
}

export function sortBySeating<T extends { party_id: string }>(
  parties: readonly T[],
): T[] {
  return [...parties].sort(
    (a, b) =>
      rank(a.party_id) - rank(b.party_id) ||
      a.party_id.localeCompare(b.party_id),
  );
}
