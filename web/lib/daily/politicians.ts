import type {
  DigestPartyPosition,
  Politician,
  PoliticianMembership,
  PoliticianMembershipLevel,
} from '@/lib/firebase/firebase.types';

const SENIORITY: PoliticianMembershipLevel[] = [
  'chair',
  'vice_chair',
  'spokesperson',
  'member',
  'deputy',
];

/** Every identified speaker of a debate, once. */
export function speakerIds(positions: DigestPartyPosition[]): string[] {
  const ids = positions.flatMap((p) =>
    p.speakers.map((s) => s.mdb_id).filter((id): id is string => !!id),
  );
  return [...new Set(ids)];
}

/** Each loaded speaker's official portrait, by MdB ID. */
export function speakerPhotos(
  politicians: Record<string, Politician> | null,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(politicians ?? {}).flatMap(([id, p]) =>
      p.photo_url ? [[id, p.photo_url]] : [],
    ),
  );
}

/** One row per Gremium of this kind, with the most senior role held in it:
 * an Obfrau is also listed as ordentliches Mitglied of the same committee. */
export function gremienOf(
  politician: Politician,
  kind: PoliticianMembership['kind'],
): PoliticianMembership[] {
  const best = new Map<string, PoliticianMembership>();
  for (const membership of politician.memberships) {
    if (membership.kind !== kind) {
      continue;
    }
    const held = best.get(membership.gremium);
    if (
      !held ||
      SENIORITY.indexOf(membership.level) < SENIORITY.indexOf(held.level)
    ) {
      best.set(membership.gremium, membership);
    }
  }
  return [...best.values()].sort(
    (a, b) => SENIORITY.indexOf(a.level) - SENIORITY.indexOf(b.level),
  );
}

/** "2021 · 2 Wahlperioden", under "Im Bundestag seit"; null without any
 * term. */
export function tenureLabel(politician: Politician): string | null {
  const years = politician.terms
    .map((t) => Number.parseInt(t.start.slice(0, 4), 10))
    .filter(Number.isFinite);
  if (years.length === 0) {
    return null;
  }
  const count = politician.terms.length;
  return `${Math.min(...years)} · ${count} ${count === 1 ? 'Wahlperiode' : 'Wahlperioden'}`;
}

/** How the member holds the seat: their Wahlkreis when won directly, else
 * the Land's list. */
export function mandateLabel(politician: Politician): string | null {
  const { wahlkreis, elected, land } = politician;
  if (elected === 'direkt' && wahlkreis) {
    return `Direkt gewählt · Wahlkreis ${wahlkreis.number} – ${wahlkreis.name}`;
  }
  if (elected === 'Landesliste' && land) {
    return `Landesliste ${land}`;
  }
  return null;
}

/** The offices under the name: "Bundesministerin · Bundesministerium für
 * …", "Parlamentarischer Geschäftsführer · Fraktion SPD". */
export function officeLines(politician: Politician): string[] {
  return politician.offices.map((office) => {
    if (office.kind === 'government') {
      return `${office.function} · ${office.institution}`;
    }
    if (office.kind === 'fraktion' && politician.fraktion) {
      return `${office.function} · Fraktion ${politician.fraktion}`;
    }
    return office.function;
  });
}

/** "Dr. Sanae Abdi". */
export function displayName(politician: Politician): string {
  return [politician.title, politician.name].filter(Boolean).join(' ');
}
