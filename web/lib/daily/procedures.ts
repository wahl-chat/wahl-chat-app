import type {
  DigestVoteParty,
  FeedItem,
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
  /** The chat question about this step. */
  question: string;
};

/** A feed item on a step's day: the debate or vote a reader can open. */
export type StepFeedLink = {
  href: string;
  kind: 'Debatte' | 'Abstimmung';
  headline: string;
  /** For a vote: the outcome and how the Fraktionen voted. */
  detail: string | null;
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
      /** Where the law stands, in one line: "Beschlossen am 13.11.26 · als
       * Nächstes: Bundesrat: Entscheidung". */
      status: string;
      /** Chat entries, the most telling first; empty while there is
       * nothing to ask about yet. */
      questions: string[];
      more: ProcedureRow[];
    }
  | { type: 'list'; rows: ProcedureRow[] };

/** What a feed card shows of its law: the type, the dots, the step. */
export type ProcedureMarker = {
  /** "Gesetz", or what the item voted on when that was not the law. */
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
function plainName(
  milestone: Pick<ProcedureMilestone, 'name' | 'chamber'>,
): string | null {
  const { name, chamber } = milestone;
  if (name.startsWith('Gesetzentwurf') || name === 'Antrag') {
    return 'Eingebracht';
  }
  if (name.startsWith('Beschlussempfehlung')) {
    return 'Ausschuss: Empfehlung';
  }
  if (chamber === 'BR') {
    if (name === '1. Durchgang') return 'Bundesrat: Stellungnahme';
    if (name === '2. Durchgang') return 'Bundesrat: Entscheidung';
    if (name === 'Durchgang') return 'Bundesrat: Entscheidung';
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
  '1. Lesung': 'Ausschuss: Empfehlung',
  'Bundesrat: Stellungnahme': 'Ausschuss: Empfehlung',
  'Ausschuss: Empfehlung': '2./3. Lesung',
  '2./3. Lesung': 'Bundesrat: Entscheidung',
  '3. Lesung': 'Bundesrat: Entscheidung',
  'Bundesrat: Entscheidung': 'Verkündung',
};

const NEXT_FACTS: Record<string, string> = {
  '1. Lesung': 'Als Nächstes berät der Bundestag den Entwurf zum ersten Mal.',
  'Ausschuss: Empfehlung':
    'Als Nächstes berät der zuständige Ausschuss den Entwurf und legt dem Bundestag eine Empfehlung vor.',
  '2./3. Lesung': 'Als Nächstes stimmt der Bundestag über das Gesetz ab.',
  'Bundesrat: Entscheidung':
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
  if (authors[0] === 'Bundesrat') {
    return 'Der Bundesrat hat den Entwurf beschlossen und dem Bundestag vorgelegt.';
  }
  const where = viaBundesrat
    ? 'zuerst dem Bundesrat, dann dem Bundestag vorgelegt'
    : 'im Bundestag eingebracht';
  return `${who} ${where}.`;
}

// The tenors DIP records for the vote on the law itself; amendments,
// resolutions and motions about the agenda have their own.
const FINAL_TENOR =
  /^(Annahme (der Vorlage|in Ausschussfassung)|Ablehnung (der Vorlagen?|in Ausschussfassung)|Erklärung der Vorlage für erledigt)/;

const MAJORITY: Record<string, string> = {
  Zweidrittelmehrheit: 'mit Zweidrittelmehrheit',
  'Absolute Mehrheit': 'mit absoluter Mehrheit',
};

/** How the Bundesrat ended its second passage; null while undecided. */
function bundesratOutcome(
  tenors: string,
): 'refused' | 'mediation' | 'agreed' | 'passed' | null {
  if (/Versagung der Zustimmung/.test(tenors)) return 'refused';
  if (/^Anrufung des Vermittlungs/m.test(tenors) || /; Anrufung/.test(tenors)) {
    return 'mediation';
  }
  if (/^Zustimmung/m.test(tenors)) return 'agreed';
  if (/kein Antrag auf Einberufung/.test(tenors)) return 'passed';
  return null;
}

function voteFacts(step: PlainStep): string {
  const decisions = decisionsOf(step);
  // The vote on the law itself, not on amendments, resolutions or motions
  // about the agenda.
  const final =
    decisions.findLast((d) => FINAL_TENOR.test(d.tenor.trim())) ?? null;
  const parts: string[] = [];
  if (final && /^Erklärung der Vorlage für erledigt/.test(final.tenor)) {
    parts.push('Der Bundestag hat den Entwurf für erledigt erklärt.');
  } else if (final) {
    const passed = final.tenor.startsWith('Annahme');
    const how = /Ausschussfassung/.test(final.tenor)
      ? ' in der Fassung des Ausschusses'
      : '';
    const majority = final.majority ? MAJORITY[final.majority] : undefined;
    const counts = tally(final.result);
    const named = final.vote_kind === 'Namentliche Abstimmung';
    parts.push(
      `${passed ? 'Angenommen' : 'Abgelehnt'}${how}${
        majority ? ` ${majority}` : ''
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
    case 'Ausschuss: Empfehlung':
      return 'Der zuständige Ausschuss hat beraten und dem Bundestag empfohlen, wie er abstimmen soll.';
    case 'Bundesrat: Entscheidung':
      switch (bundesratOutcome(decisions.map((d) => d.tenor).join('\n'))) {
        case 'refused':
          return 'Der Bundesrat hat dem Gesetz nicht zugestimmt.';
        case 'mediation':
          return 'Der Bundesrat hat den Vermittlungsausschuss angerufen.';
        case 'agreed':
          return 'Der Bundesrat hat dem Gesetz zugestimmt.';
        case 'passed':
          return 'Der Bundesrat hat den Vermittlungsausschuss nicht angerufen. Das Gesetz kann damit verkündet werden.';
        default:
          return 'Der Bundesrat hat über das beschlossene Gesetz beraten.';
      }
    case 'Verkündet':
      return 'Das Gesetz wurde im Bundesgesetzblatt verkündet.';
    default:
      return isVote(step.label) ? voteFacts(step) : '';
  }
}

/** The step's PDF at its page; DIP's own anchor names the printed page. */
export function stepHref(url: string, page?: number | null): string {
  const bare = url.split('#')[0];
  return page ? `${bare}#page=${page}` : bare;
}

function stepLinks(step: PlainStep): StepLink[] {
  const seen = new Set<string>();
  const links: StepLink[] = [];
  for (const m of step.milestones) {
    if (!m.url?.startsWith('https://') || !m.document_number) continue;
    if (seen.has(m.document_number)) continue;
    seen.add(m.document_number);
    links.push({
      label: `${m.document_kind ?? 'Dokument'} ${m.document_number}`,
      href: stepHref(m.url, m.pdf_page),
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
    case 'Ausschuss: Empfehlung':
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
        i > from && s.label === 'Ausschuss: Empfehlung' && s.state !== 'next',
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
  // Two at most: the chat entry below the item brings its own questions.
  return out.slice(0, 2);
}

/** The step's facts and summary; a committee's generic line gives way to
 * the summary of what it recommends. */
function withSummary(
  step: PlainStep,
  procedure: ProcedureSummary,
): { facts: string; summary: string | null } {
  const summary =
    step.milestones.find((m) => m.chamber === 'BT' && m.summary)?.summary ??
    null;
  const generic = step.label === 'Ausschuss: Empfehlung';
  return {
    facts: summary && generic ? '' : stepFacts(step, procedure),
    summary,
  };
}

const statusDay = new Intl.DateTimeFormat('de-DE', {
  day: '2-digit',
  month: '2-digit',
  year: '2-digit',
  timeZone: 'UTC',
});

/** A Bundestag vote the law passed: by DIP's tally, or by its status. */
export function passedVote(
  step: TimelineStep,
  procedure: ProcedureSummary,
): boolean {
  return (
    isVote(step.label) &&
    (step.facts.startsWith('Angenommen') ||
      procedure.beratungsstand === 'Verabschiedet')
  );
}

function statusLine(
  steps: TimelineStep[],
  procedure: ProcedureSummary,
): string {
  const last = steps.findLast((s) => s.state !== 'next');
  const next = steps.find((s) => s.state === 'next');
  if (!last?.date) return '';
  const day = statusDay.format(new Date(`${last.date}T00:00:00Z`));
  const where =
    last.label === 'Verkündet'
      ? `Verkündet am ${day}`
      : passedVote(last, procedure)
        ? `Im Bundestag beschlossen am ${day}`
        : `Stand: ${last.label} am ${day}`;
  return next ? `${where} · als Nächstes: ${next.label}` : where;
}

/** A vote on an amendment or resolution to the law, not on the law. */
export function votedOnAmendment(voteTitle: string | undefined): boolean {
  return /\((Änderungsantrag|Entschließungsantrag)\)\s*$/.test(voteTitle ?? '');
}

/** What the detail view shows for an item's procedures:
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
  const onItemDay = (s: PlainStep) =>
    s.chamber === 'BT' && s.date === day && s.label !== 'Eingebracht';
  // A committee report dated the day of the vote: the vote is the item's step.
  const voteIndex = plain.findIndex((s) => onItemDay(s) && isVote(s.label));
  const hereIndex =
    voteIndex >= 0 ? voteIndex : plain.findIndex((s) => onItemDay(s));
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
    ...withSummary(s, main),
    links: stepLinks(s),
    question: stepQuestion(s),
  }));
  const lastTenors = (plain.at(-1)?.milestones ?? [])
    .flatMap((m) => m.decisions ?? [])
    .map((d) => d.tenor)
    .join('\n');
  // After a refusal or a call for mediation, no step follows as a rule.
  const stalled = ['refused', 'mediation'].includes(
    bundesratOutcome(lastTenors) ?? '',
  );
  const finished =
    stalled ||
    DEAD.test(main.beratungsstand ?? '') ||
    plain.at(-1)?.label === 'Verkündet';
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
      question: 'Was passiert als Nächstes?',
    });
  }
  return {
    type: 'timeline',
    main,
    steps,
    status: statusLine(steps, main),
    questions: sectionQuestions(steps),
    more: shown.filter((p) => p !== main).map(row),
  };
}

/** The type tag, dots and current step a feed card shows; null without a
 * law to follow. The step is the item's own, else the law's newest. */
export function procedureMarker(
  day: string,
  procedures: ProcedureSummary[] | undefined,
  voteTitle?: string,
): ProcedureMarker | null {
  const section = procedureSection(day, procedures);
  if (section?.type !== 'timeline') return null;
  const { steps } = section;
  const current =
    steps.find((s) => s.state === 'here') ??
    steps.findLast((s) => s.state !== 'next');
  if (!current) return null;
  return {
    tag: votedOnAmendment(voteTitle) ? 'Änderungsantrag zum Gesetz' : 'Gesetz',
    states: steps.map((s) => s.state),
    step: current.label,
  };
}

/** A procedure's latest step as the timeline names it; the third reading
 * is held with the second. */
export function plainStageName(name: string): string {
  const chamber = /Durchgang/.test(name) ? 'BR' : 'BT';
  const label = plainName({ name, chamber }) ?? name;
  return label === '3. Lesung' ? '2./3. Lesung' : label;
}

const STANCES = [
  ['yes', 'Ja'],
  ['no', 'Nein'],
  ['abstain', 'Enthalten'],
] as const;

/** "Ja: CDU/CSU, SPD · Nein: AfD, Die Linke": each Fraktion by how most of
 * its members voted. */
export function fractionLine(parties: DigestVoteParty[]): string {
  const by = new Map<string, string[]>();
  for (const party of parties) {
    if (party.party_id === 'fraktionslos') continue;
    const counts = STANCES.map(([key]) => Number(party[key]) || 0);
    const top = Math.max(...counts);
    if (top === 0) continue;
    const label = STANCES[counts.indexOf(top)][1];
    by.set(label, [...(by.get(label) ?? []), party.name]);
  }
  return STANCES.flatMap(([, label]) =>
    by.has(label) ? [`${label}: ${by.get(label)?.join(', ')}`] : [],
  ).join(' · ');
}

// Bundestag steps that take place in the plenary, where the feed has items.
const PLENARY = (label: string) => label === '1. Lesung' || isVote(label);

/** The feed's items on a step's day, other than the one being read. */
export function stepFeedLinks(
  step: TimelineStep,
  items: FeedItem[],
  currentId: string,
  href: (item: FeedItem) => string,
): StepFeedLink[] {
  if (!step.date || !PLENARY(step.label)) return [];
  return items
    .filter(
      (item) =>
        item.date === step.date &&
        item.status === 'published' &&
        item.id !== currentId,
    )
    .sort((a, b) =>
      a.kind === b.kind ? a.rank - b.rank : a.kind === 'vote' ? -1 : 1,
    )
    .map((item) => ({
      href: href(item),
      kind: item.kind === 'vote' ? 'Abstimmung' : 'Debatte',
      headline: item.content.de.headline,
      detail: item.vote
        ? [
            item.vote.outcome === 'angenommen'
              ? 'Angenommen'
              : item.vote.outcome === 'abgelehnt'
                ? 'Abgelehnt'
                : null,
            fractionLine(item.vote.parties),
          ]
            .filter(Boolean)
            .join('. ')
        : null,
    }));
}

/** The general chat about one procedure, with the question already asked;
 * `from` is the feed item to go back to. */
export function procedureChatHref(
  vorgangId: string,
  question: string,
  from?: string,
): string {
  const params = new URLSearchParams({
    procedure: vorgangId,
    q: question,
    preset: 'ask',
  });
  if (from) params.set('from', from);
  return `/chat?${params}`;
}
