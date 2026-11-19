import type {
  DigestPartyPosition,
  FeedLocale,
  Politician,
  PoliticianMembership,
  PoliticianMembershipLevel,
} from '@/lib/firebase/firebase.types';

/** The labels around a record's own texts, in the reader's language. */
export type PoliticianWords = {
  /** "2021 · 2 Wahlperioden" */
  tenure: (since: number, terms: number) => string;
  /** "Direkt gewählt · Wahlkreis 092 – Köln I" */
  direct: (number: string, name: string) => string;
  /** "Landesliste Nordrhein-Westfalen" */
  list: (land: string) => string;
  /** "Fraktion SPD" */
  fraktion: (name: string) => string;
};

/**
 * The record with its texts in `locale` where the feed job has translated
 * them. Each text is looked up on its own, so one still waiting for its
 * translation stays German while the rest are already in English.
 */
export function localizedPolitician(
  politician: Politician,
  locale: FeedLocale,
): Politician {
  if (locale === 'de') {
    return politician;
  }
  const texts = new Map(
    (politician.translations?.[locale]?.texts ?? []).map((t) => [
      t.source,
      t.text,
    ]),
  );
  if (texts.size === 0) {
    return politician;
  }
  const tr = (text: string) => texts.get(text) ?? text;
  const trOrNull = (text: string | null) => (text === null ? null : tr(text));
  const { disclosures } = politician;
  return {
    ...politician,
    beruf: trOrNull(politician.beruf),
    offices: politician.offices.map((office) => ({
      ...office,
      function: tr(office.function),
      institution: tr(office.institution),
    })),
    memberships: politician.memberships.map((membership) => ({
      ...membership,
      gremium: tr(membership.gremium),
      role: tr(membership.role),
    })),
    votes: politician.votes?.map((vote) => ({
      ...vote,
      title: tr(vote.title),
    })),
    disclosures: disclosures && {
      ...disclosures,
      note: trOrNull(disclosures.note),
      link_phrase: trOrNull(disclosures.link_phrase),
      sections: disclosures.sections.map((section) => ({
        ...section,
        heading: trOrNull(section.heading),
      })),
    },
  };
}

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
export function tenureLabel(
  politician: Politician,
  words: PoliticianWords,
): string | null {
  const years = politician.terms
    .map((t) => Number.parseInt(t.start.slice(0, 4), 10))
    .filter(Number.isFinite);
  if (years.length === 0) {
    return null;
  }
  return words.tenure(Math.min(...years), politician.terms.length);
}

/** How the member holds the seat: their Wahlkreis when won directly, else
 * the Land's list. */
export function mandateLabel(
  politician: Politician,
  words: PoliticianWords,
): string | null {
  const { wahlkreis, elected, land } = politician;
  if (elected === 'direkt' && wahlkreis) {
    return words.direct(wahlkreis.number, wahlkreis.name);
  }
  if (elected === 'Landesliste' && land) {
    return words.list(land);
  }
  return null;
}

/** The offices under the name: "Bundesministerin · Bundesministerium für
 * …", "Parlamentarischer Geschäftsführer · Fraktion SPD". */
export function officeLines(
  politician: Politician,
  words: PoliticianWords,
): string[] {
  return politician.offices.map((office) => {
    if (office.kind === 'government') {
      return `${office.function} · ${office.institution}`;
    }
    if (office.kind === 'fraktion' && politician.fraktion) {
      return `${office.function} · ${words.fraktion(politician.fraktion)}`;
    }
    return office.function;
  });
}

/** "Dr. Sanae Abdi". */
export function displayName(politician: Politician): string {
  return [politician.title, politician.name].filter(Boolean).join(' ');
}
