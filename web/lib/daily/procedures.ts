import type {
  ProcedureMilestone,
  ProcedureSummary,
  StageDecision,
} from '@/lib/firebase/firebase.types';

export type StepLink = { label: string; href: string };

/** One step of the timeline. `here` is this feed item's step; `latest` the
 * procedure's newest step when it lies after `here`; `next` the usual next
 * step, not yet taken. */
export type TimelineStep = {
  /** ISO day; null for `next`. */
  date: string | null;
  label: string;
  state: 'done' | 'here' | 'latest' | 'next';
  /** What happened, from DIP's record alone. */
  facts: string;
  /** A checked model summary of the step's Drucksache. */
  summary: string | null;
  links: StepLink[];
  /** The chat question about this step; null for `next`. */
  question: string | null;
};

export type ProcedureRow = {
  procedure: ProcedureSummary;
  /** "Fraktion der SPD" → "SPD"; empty when the summary has no initiative. */
  authors: string[];
  status: string | null;
};

export type ProcedureSection =
  | {
      type: 'timeline';
      main: ProcedureSummary;
      steps: TimelineStep[];
      /** Chat entries, the most telling first; empty while there is
       * nothing to ask about yet. */
      questions: string[];
      more: ProcedureRow[];
    }
  | { type: 'list'; rows: ProcedureRow[] };

/** What a feed card shows of its law: the type, the dots, the step. */
export type ProcedureMarker = {
  tag: string;
  states: TimelineStep['state'][];
  step: string;
};

// Bookkeeping kinds: petitions, reports, elections. Not what a reader follows.
const HIDDEN_KINDS = new Set<ProcedureSummary['kind']>([
  'procedural',
  'report',
  'questions',
]);

const READINGS = new Set(['2. Beratung', '3. Beratung']);

// Finished without passing (DIP Beratungsstand).
const DEAD = /^(Erledigt|Abgelehnt|Zurückgezogen|Für erledigt erklärt)/;

/** DIP's step names in plain words. */
function plainName(milestone: ProcedureMilestone): string | null {
  const { name, chamber } = milestone;
  if (name.startsWith('Gesetzentwurf') || name === 'Antrag') {
    return 'Eingebracht';
  }
  if (name.startsWith('Beschlussempfehlung')) {
    return 'Ausschuss: Beschlussempfehlung';
  }
  if (chamber === 'BR') {
    if (name === '1. Durchgang') return 'Bundesrat: Stellungnahme';
    if (name === '2. Durchgang') return 'Bundesrat: 2. Durchgang';
    if (name === 'Durchgang') return 'Bundesrat';
    return null;
  }
  if (name === '1. Beratung') return '1. Lesung';
  if (name === '2. Beratung') return '2. Lesung';
  if (name === '3. Beratung') return '3. Lesung';
  if (name.startsWith('Verkündung')) return 'Verkündet';
  if (name.startsWith('Entschließungsantrag')) return null;
  return name;
}

const NEXT_FOR_LAW: Record<string, string> = {
  Eingebracht: '1. Lesung',
  '1. Lesung': 'Ausschuss: Beschlussempfehlung',
  'Bundesrat: Stellungnahme': 'Ausschuss: Beschlussempfehlung',
  'Ausschuss: Beschlussempfehlung': '2./3. Lesung',
  '2./3. Lesung': 'Bundesrat: 2. Durchgang',
  '3. Lesung': 'Bundesrat: 2. Durchgang',
  'Bundesrat: 2. Durchgang': 'Verkündung',
  Bundesrat: 'Verkündung',
};

const NEXT_FACTS: Record<string, string> = {
  '1. Lesung': 'Als Nächstes berät der Bundestag den Entwurf zum ersten Mal.',
  'Ausschuss: Beschlussempfehlung':
    'Als Nächstes berät der zuständige Ausschuss den Entwurf und legt dem Bundestag eine Empfehlung vor.',
  '2./3. Lesung': 'Als Nächstes stimmt der Bundestag über das Gesetz ab.',
  'Bundesrat: 2. Durchgang':
    'Als Nächstes berät der Bundesrat das beschlossene Gesetz.',
  Verkündung:
    'Als Nächstes unterschreibt der Bundespräsident, dann wird das Gesetz verkündet.',
};

const isVote = (label: string) =>
  label === '2./3. Lesung' || label === '2. Lesung' || label === '3. Lesung';

type PlainStep = {
  date: string;
  label: string;
  chamber: string;
  milestones: ProcedureMilestone[];
};

/** Plain steps, oldest first: "Eingebracht" once (its first date), a
 * same-day 2. and 3. Beratung merged into "2./3. Lesung". */
export function timelineSteps(milestones: ProcedureMilestone[]): PlainStep[] {
  const steps: PlainStep[] = [];
  const sorted = [...milestones].sort((a, b) => a.date.localeCompare(b.date));
  for (const milestone of sorted) {
    const label = plainName(milestone);
    if (!label) continue;
    const introduced = steps.find((s) => s.label === 'Eingebracht');
    if (label === 'Eingebracht' && introduced) {
      introduced.milestones.push(milestone);
      continue;
    }
    const last = steps.at(-1);
    if (
      last &&
      last.date === milestone.date &&
      READINGS.has(milestone.name) &&
      (last.label === '2. Lesung' || last.label === '2./3. Lesung')
    ) {
      last.label = '2./3. Lesung';
      last.milestones.push(milestone);
      continue;
    }
    if (last && last.date === milestone.date && last.label === label) {
      last.milestones.push(milestone);
      continue;
    }
    steps.push({
      date: milestone.date,
      label,
      chamber: milestone.chamber,
      milestones: [milestone],
    });
  }
  return steps;
}

function plainAuthors(initiative: string[] | undefined): string[] {
  return (initiative ?? []).map((name) =>
    name
      .replace(/^Fraktion (der |des )?/, '')
      .replace(/^BÜNDNIS 90\/DIE GRÜNEN$/, 'Grüne'),
  );
}

function listed(names: string[]): string {
  if (names.length <= 1) return names.join('');
  return `${names.slice(0, -1).join(', ')} und ${names.at(-1)}`;
}

/** "308:190:71" → "308 Ja, 190 Nein, 71 Enthaltungen". */
function tally(result: string | null): string | null {
  const match = result?.match(/^(\d+):(\d+):(\d+)$/);
  if (!match) return null;
  const [, yes, no, abstain] = match;
  return `${yes} Ja, ${no} Nein, ${abstain} Enthaltungen`;
}

function decisionsOf(step: PlainStep): StageDecision[] {
  return step.milestones.flatMap((m) => m.decisions ?? []);
}

function introducedFacts(step: PlainStep, procedure: ProcedureSummary): string {
  const authors = plainAuthors(procedure.initiative);
  const who =
    authors.length === 0
      ? 'Der Entwurf wurde'
      : authors[0] === 'Bundesregierung'
        ? 'Die Bundesregierung hat den Entwurf'
        : authors[0] === 'Bundesrat'
          ? 'Der Bundesrat hat den Entwurf'
          : `${listed(authors)} ${authors.length > 1 ? 'haben' : 'hat'} den Entwurf`;
  const viaBundesrat =
    step.milestones.some((m) => m.chamber === 'BR') &&
    step.milestones.some((m) => m.chamber === 'BT');
  const where = viaBundesrat
    ? 'zuerst dem Bundesrat, dann dem Bundestag vorgelegt'
    : 'im Bundestag eingebracht';
  return `${who} ${where}.`;
}

function voteFacts(step: PlainStep): string {
  const decisions = decisionsOf(step);
  // The vote on the law itself, not on amendments, resolutions or motions
  // about the agenda.
  const final =
    decisions.findLast(
      (d) =>
        /^(Annahme|Ablehnung)/.test(d.tenor) &&
        !/Änderungsantrag|Entschließung|Geschäftsordnung/.test(d.tenor),
    ) ?? null;
  const parts: string[] = [];
  if (final) {
    const passed = final.tenor.startsWith('Annahme');
    const how = /Ausschussfassung/.test(final.tenor)
      ? ' in der Fassung des Ausschusses'
      : '';
    const counts = tally(final.result);
    const named = final.vote_kind === 'Namentliche Abstimmung';
    parts.push(
      `${passed ? 'Angenommen' : 'Abgelehnt'}${how}${
        final.majority ? ` mit ${final.majority}` : ''
      }${counts ? `: ${counts}${named ? ' (namentliche Abstimmung)' : ''}` : ''}.`,
    );
  } else {
    parts.push('Der Bundestag hat abschließend über das Gesetz beraten.');
  }
  const amendments = decisions.filter((d) =>
    d.tenor.startsWith('Ablehnung des Änderungsantrags'),
  ).length;
  if (amendments === 1) parts.push('Ein Änderungsantrag wurde abgelehnt.');
  if (amendments > 1)
    parts.push(`${amendments} Änderungsanträge wurden abgelehnt.`);
  if (
    decisions.some((d) => d.tenor.startsWith('Annahme einer Entschließung'))
  ) {
    parts.push('Dazu wurde eine Entschließung angenommen.');
  }
  return parts.join(' ');
}

function stepFacts(step: PlainStep, procedure: ProcedureSummary): string {
  const decisions = decisionsOf(step);
  const tenors = decisions.map((d) => d.tenor).join(' ');
  switch (step.label) {
    case 'Eingebracht':
      return introducedFacts(step, procedure);
    case '1. Lesung':
      return /Überweisung/.test(tenors)
        ? 'Erste Debatte im Bundestag. Danach wurde der Entwurf an die Ausschüsse überwiesen.'
        : 'Erste Debatte im Bundestag.';
    case 'Bundesrat: Stellungnahme':
      return /keine Einwendungen/i.test(tenors)
        ? 'Der Bundesrat hat keine Einwände gegen den Entwurf erhoben.'
        : 'Der Bundesrat hat zum Entwurf Stellung genommen.';
    case 'Ausschuss: Beschlussempfehlung':
      return 'Der zuständige Ausschuss hat beraten und dem Bundestag empfohlen, wie er abstimmen soll.';
    case 'Bundesrat: 2. Durchgang':
    case 'Bundesrat':
      if (/Zustimmung/.test(tenors))
        return 'Der Bundesrat hat dem Gesetz zugestimmt.';
      if (/Einberufung des Vermittlungsausschusses/.test(tenors)) {
        return /kein Antrag/i.test(tenors)
          ? 'Der Bundesrat hat das Gesetz passieren lassen.'
          : 'Der Bundesrat hat den Vermittlungsausschuss angerufen.';
      }
      return 'Der Bundesrat hat über das beschlossene Gesetz beraten.';
    case 'Verkündet':
      return 'Das Gesetz wurde im Bundesgesetzblatt verkündet und gilt damit.';
    default:
      return isVote(step.label) ? voteFacts(step) : '';
  }
}

function stepLinks(step: PlainStep): StepLink[] {
  const seen = new Set<string>();
  const links: StepLink[] = [];
  for (const m of step.milestones) {
    if (!m.url || !m.document_number || seen.has(m.document_number)) continue;
    seen.add(m.document_number);
    links.push({
      label: `${m.document_kind ?? 'Dokument'} ${m.document_number}`,
      href: m.url,
    });
  }
  return links;
}

const shortDay = new Intl.DateTimeFormat('de-DE', {
  day: '2-digit',
  month: '2-digit',
  timeZone: 'UTC',
});

function stepQuestion(step: PlainStep): string {
  const day = shortDay.format(new Date(`${step.date}T00:00:00Z`));
  switch (step.label) {
    case 'Eingebracht':
      return 'Was sieht der Entwurf vor?';
    case '1. Lesung':
      return `Was wurde in der 1. Lesung am ${day} gesagt?`;
    case 'Bundesrat: Stellungnahme':
      return 'Was hat der Bundesrat zum Entwurf gesagt?';
    case 'Ausschuss: Beschlussempfehlung':
      return 'Was hat der Ausschuss am Entwurf geändert?';
    case 'Verkündet':
      return 'Ab wann gilt das Gesetz?';
    default:
      return isVote(step.label)
        ? `Wie haben die Fraktionen am ${day} abgestimmt?`
        : `Was ist am ${day} passiert?`;
  }
}

function authorsOf(procedure: ProcedureSummary): string[] {
  return plainAuthors(procedure.initiative);
}

function statusOf(procedure: ProcedureSummary): string | null {
  const status = procedure.beratungsstand;
  if (!status) return null;
  if (status === 'Überwiesen') return 'An Ausschuss überwiesen';
  return status;
}

function row(procedure: ProcedureSummary): ProcedureRow {
  return {
    procedure,
    authors: authorsOf(procedure),
    status: statusOf(procedure),
  };
}

function onDay(procedure: ProcedureSummary, day: string): boolean {
  return procedure.milestones.some((m) => m.chamber === 'BT' && m.date === day);
}

/** The section's chat entries: what a reader most likely wants next. */
function sectionQuestions(steps: TimelineStep[]): string[] {
  const hereIndex = steps.findIndex((s) => s.state === 'here');
  const taken = steps.filter((s) => s.state !== 'next');
  if (taken.length <= 1) {
    return taken.length === 1 ? ['Worum geht es im Entwurf?'] : [];
  }
  const nextStep = steps.find((s) => s.state === 'next');
  const committee = (from: number) =>
    steps.some(
      (s, i) =>
        i > from &&
        s.label === 'Ausschuss: Beschlussempfehlung' &&
        s.state !== 'next',
    );
  const here = hereIndex >= 0 ? steps[hereIndex] : null;
  const movedOn = steps.some((s) => s.state === 'latest');
  const out: string[] = [];
  if (here && isVote(here.label)) {
    if (committee(-1)) out.push('Was wurde am Entwurf geändert?');
    out.push('Wie kam das Gesetz zustande?');
    if (nextStep?.label.startsWith('Bundesrat')) {
      out.push('Was passiert jetzt im Bundesrat?');
    }
  } else if (movedOn) {
    out.push('Wie ging es weiter?');
    if (committee(hereIndex)) out.push('Was wurde am Entwurf geändert?');
  } else {
    out.push('Worum geht es im Entwurf?');
    if (nextStep) out.push('Was passiert als Nächstes?');
  }
  return out.slice(0, 3);
}

/** What the detail view shows for an item's procedures (see flows F-11):
 * a law gets a timeline with the item's step highlighted, a debate on
 * Anträge only a list, anything else nothing. */
export function procedureSection(
  day: string,
  procedures: ProcedureSummary[] | undefined,
): ProcedureSection | null {
  const shown = (procedures ?? []).filter((p) => !HIDDEN_KINDS.has(p.kind));
  const laws = shown.filter((p) => p.kind === 'legislation');
  const main = laws.find((p) => onDay(p, day)) ?? laws[0];
  if (!main) {
    return shown.length > 0 ? { type: 'list', rows: shown.map(row) } : null;
  }

  const plain = timelineSteps(main.milestones);
  const hereIndex = plain.findIndex(
    (s) => s.chamber === 'BT' && s.date === day && s.label !== 'Eingebracht',
  );
  const lastIndex = plain.length - 1;
  const steps: TimelineStep[] = plain.map((s, i) => ({
    date: s.date,
    label: s.label,
    state:
      i === hereIndex
        ? 'here'
        : i === lastIndex && hereIndex >= 0 && i > hereIndex
          ? 'latest'
          : 'done',
    facts: stepFacts(s, main),
    summary:
      s.milestones.find((m) => m.chamber === 'BT' && m.summary)?.summary ??
      null,
    links: stepLinks(s),
    question: stepQuestion(s),
  }));
  const finished =
    DEAD.test(main.beratungsstand ?? '') || plain.at(-1)?.label === 'Verkündet';
  const next =
    plain.length > 0 ? NEXT_FOR_LAW[plain[lastIndex].label] : undefined;
  if (next && !finished) {
    steps.push({
      date: null,
      label: next,
      state: 'next',
      facts:
        `${NEXT_FACTS[next] ?? ''} Ein Termin steht noch nicht fest.`.trim(),
      summary: null,
      links: [],
      question: null,
    });
  }
  return {
    type: 'timeline',
    main,
    steps,
    questions: sectionQuestions(steps),
    more: shown.filter((p) => p !== main).map(row),
  };
}

/** The type tag, dots and current step a feed card shows; null without a
 * law to follow. The step is the item's own, else the law's newest. */
export function procedureMarker(
  day: string,
  procedures: ProcedureSummary[] | undefined,
): ProcedureMarker | null {
  const section = procedureSection(day, procedures);
  if (section?.type !== 'timeline') return null;
  const { steps } = section;
  const current =
    steps.find((s) => s.state === 'here') ??
    steps.findLast((s) => s.state !== 'next');
  if (!current) return null;
  return {
    tag: 'Gesetz',
    states: steps.map((s) => s.state),
    step: current.label,
  };
}

/** The general chat about one procedure, with the question already asked. */
export function procedureChatHref(vorgangId: string, question: string): string {
  const params = new URLSearchParams({ procedure: vorgangId, q: question });
  return `/chat?${params}`;
}
