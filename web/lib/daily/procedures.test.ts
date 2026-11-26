import { describe, expect, it } from 'bun:test';
import type {
  DigestVoteParty,
  FeedItem,
  ProcedureSummary,
  StageDecision,
} from '@/lib/firebase/firebase.types';
import {
  type TimelineStep,
  fractionLine,
  plainStageName,
  procedureChatHref,
  procedureMarker,
  procedureSection,
  stepFeedLinks,
  stepHref,
  timelineSteps,
} from './procedures';

function law(
  id: string,
  milestones: [string, 'BT' | 'BR', string][],
  extra: Partial<ProcedureSummary> = {},
): ProcedureSummary {
  return {
    vorgang_id: id,
    titel: `Gesetz ${id}`,
    vorgangstyp: 'Gesetzgebung',
    kind: 'legislation',
    beratungsstand: 'Beschlussempfehlung liegt vor',
    latest_stage: null,
    latest_stage_on: null,
    stage_changed_on: null,
    milestones: milestones.map(([date, chamber, name]) => ({
      date,
      chamber,
      name,
    })),
    dip_url: `https://dip.bundestag.de/vorgang/gesetz-${id}/${id}`,
    ...extra,
  };
}

function motion(
  id: string,
  extra: Partial<ProcedureSummary> = {},
): ProcedureSummary {
  return {
    ...law(id, [['2026-11-06', 'BT', 'Antrag']]),
    kind: 'motion',
    vorgangstyp: 'Antrag',
    ...extra,
  };
}

// Startchancen-Gesetz, as DIP lists it.
const PASSED = law(
  '338785',
  [
    ['2026-09-04', 'BR', 'Gesetzentwurf'],
    ['2026-09-28', 'BT', 'Gesetzentwurf'],
    ['2026-10-09', 'BT', '1. Beratung'],
    ['2026-10-16', 'BR', '1. Durchgang'],
    ['2026-11-11', 'BT', 'Beschlussempfehlung und Bericht'],
    ['2026-11-12', 'BT', '2. Beratung'],
    ['2026-11-12', 'BT', '3. Beratung'],
  ],
  { beratungsstand: 'Verabschiedet' },
);

// Haushaltsbegleitgesetz 2027: debated 08.09., committee report 16.11.
const IN_COMMITTEE = law('338366', [
  ['2026-08-14', 'BR', 'Gesetzentwurf'],
  ['2026-09-07', 'BT', 'Gesetzentwurf'],
  ['2026-09-08', 'BT', '1. Beratung'],
  ['2026-09-25', 'BR', '1. Durchgang'],
  ['2026-11-16', 'BT', 'Beschlussempfehlung und Bericht'],
]);

describe('timelineSteps', () => {
  it('names steps plainly, introduces once and merges 2./3. Beratung', () => {
    expect(
      timelineSteps(PASSED.milestones).map((s) => [s.date, s.label]),
    ).toEqual([
      ['2026-09-04', 'Eingebracht'],
      ['2026-10-09', '1. Lesung'],
      ['2026-10-16', 'Bundesrat: Stellungnahme'],
      ['2026-11-11', 'Ausschuss: Empfehlung'],
      ['2026-11-12', '2./3. Lesung'],
    ]);
  });
});

describe('procedureSection', () => {
  it('highlights the vote and expects the Bundesrat next', () => {
    const section = procedureSection('2026-11-12', [PASSED]);
    expect(section?.type).toBe('timeline');
    if (section?.type !== 'timeline') return;
    expect(section.steps.map((s) => [s.label, s.state])).toEqual([
      ['Eingebracht', 'done'],
      ['1. Lesung', 'done'],
      ['Bundesrat: Stellungnahme', 'done'],
      ['Ausschuss: Empfehlung', 'done'],
      ['2./3. Lesung', 'here'],
      ['Bundesrat: Entscheidung', 'next'],
    ]);
    expect(section.questions).toEqual([
      'Was wurde am Entwurf geändert?',
      'Wie kam das Gesetz zustande?',
    ]);
    expect(section.status).toBe(
      'Im Bundestag beschlossen am 12.11.26 · als Nächstes: Bundesrat: Entscheidung',
    );
  });

  it('marks the latest step after a debate and asks how it went on', () => {
    const section = procedureSection('2026-09-08', [IN_COMMITTEE]);
    if (section?.type !== 'timeline') throw new Error('timeline expected');
    expect(section.steps.find((s) => s.state === 'here')?.label).toBe(
      '1. Lesung',
    );
    expect(section.steps.find((s) => s.state === 'latest')?.label).toBe(
      'Ausschuss: Empfehlung',
    );
    expect(section.steps.at(-1)).toEqual(
      expect.objectContaining({
        date: null,
        label: '2./3. Lesung',
        state: 'next',
        question: 'Was passiert als Nächstes?',
      }),
    );
    expect(section.questions).toEqual([
      'Wie ging es weiter?',
      'Was wurde am Entwurf geändert?',
    ]);
  });

  it('picks the law read that day and keeps the rest under "weitere"', () => {
    const resolution = motion('9', {
      titel: 'Entschließungsantrag zum Gesetz 338366',
    });
    const section = procedureSection('2026-09-08', [
      PASSED,
      resolution,
      IN_COMMITTEE,
    ]);
    if (section?.type !== 'timeline') throw new Error('timeline expected');
    expect(section.main.vorgang_id).toBe('338366');
    expect(section.more.map((r) => r.procedure.vorgang_id)).toEqual([
      '338785',
      '9',
    ]);
  });

  it('lists Anträge without a timeline, with authors and status', () => {
    const section = procedureSection('2026-11-06', [
      motion('1', {
        initiative: ['Fraktion der CDU/CSU', 'Fraktion der SPD'],
        beratungsstand: 'Angenommen',
      }),
      motion('2', {
        initiative: ['Fraktion BÜNDNIS 90/DIE GRÜNEN'],
        beratungsstand: 'Überwiesen',
      }),
    ]);
    expect(section).toEqual({
      type: 'list',
      rows: [
        expect.objectContaining({
          authors: ['CDU/CSU', 'SPD'],
          status: 'Angenommen',
        }),
        expect.objectContaining({
          authors: ['Grüne'],
          status: 'An Ausschuss überwiesen',
        }),
      ],
    });
  });

  it('shows nothing for bookkeeping procedures or none', () => {
    expect(procedureSection('2026-11-06', undefined)).toBeNull();
    expect(
      procedureSection('2026-11-06', [
        motion('3', { kind: 'procedural' }),
        motion('4', { kind: 'report' }),
      ]),
    ).toBeNull();
  });

  it('expects nothing after a procedure that ended', () => {
    const dead = {
      ...IN_COMMITTEE,
      beratungsstand: 'Erledigt durch Ablauf der Wahlperiode',
    };
    const section = procedureSection('2026-09-08', [dead]);
    if (section?.type !== 'timeline') throw new Error('timeline expected');
    expect(section.steps.some((s) => s.state === 'next')).toBe(false);
  });

  it('asks what the draft is about while it was only introduced', () => {
    const fresh = law('5', [['2026-11-01', 'BT', 'Gesetzentwurf']]);
    const section = procedureSection('2026-11-01', [fresh]);
    if (section?.type !== 'timeline') throw new Error('timeline expected');
    expect(section.questions).toEqual(['Worum geht es im Entwurf?']);
  });

  it('asks about the draft and what comes next after a latest debate', () => {
    const section = procedureSection('2026-11-16', [IN_COMMITTEE]);
    if (section?.type !== 'timeline') throw new Error('timeline expected');
    expect(section.questions).toEqual([
      'Worum geht es im Entwurf?',
      'Was passiert als Nächstes?',
    ]);
  });
});

describe('procedureChatHref', () => {
  it('opens the general chat with the procedure attached and the button question', () => {
    expect(procedureChatHref('338366', 'Wie ging es weiter?')).toBe(
      '/chat?procedure=338366&q=Wie+ging+es+weiter%3F&preset=ask',
    );
  });
});

// Reform des Nachrichtendienstrechts: DIP lists the 2. Beratung twice, the
// decisions of the day on both entries.
const VOTED: ProcedureSummary = {
  ...law('338341', []),
  initiative: ['Bundesregierung'],
  milestones: [
    {
      date: '2026-08-14',
      chamber: 'BR',
      name: 'Gesetzentwurf',
      document_kind: 'Drucksache',
      document_number: '453/26',
      url: 'https://dserver.bundestag.de/brd/2026/0453-26.pdf',
    },
    {
      date: '2026-09-07',
      chamber: 'BT',
      name: 'Gesetzentwurf',
      document_kind: 'Drucksache',
      document_number: '21/7868',
      url: 'https://dserver.bundestag.de/btd/21/078/2107868.pdf',
      summary:
        'Die Bundesregierung will das Verfassungsschutzgesetz neu fassen.',
    },
    {
      date: '2026-09-24',
      chamber: 'BT',
      name: '1. Beratung',
      decisions: [
        { tenor: 'Überweisung', vote_kind: null, result: null, majority: null },
      ],
    },
    {
      date: '2026-11-11',
      chamber: 'BT',
      name: 'Beschlussempfehlung und Bericht',
      document_kind: 'Drucksache',
      document_number: '21/9161',
      url: 'https://dserver.bundestag.de/btd/21/091/2109161.pdf',
      summary: 'Der Innenausschuss empfiehlt Änderungen.',
    },
    {
      date: '2026-11-13',
      chamber: 'BT',
      name: '2. Beratung',
      decisions: [
        {
          tenor: 'Ablehnung des Änderungsantrags',
          vote_kind: 'Namentliche Abstimmung',
          result: '257:313:2',
          majority: null,
        },
        {
          tenor: 'Ablehnung des Änderungsantrags',
          vote_kind: 'Namentliche Abstimmung',
          result: '207:313:52',
          majority: null,
        },
        {
          tenor: 'Annahme in Ausschussfassung',
          vote_kind: null,
          result: null,
          majority: null,
        },
        {
          tenor: 'Annahme einer Entschließung',
          vote_kind: null,
          result: null,
          majority: null,
        },
      ],
    },
    {
      date: '2026-11-13',
      chamber: 'BT',
      name: '3. Beratung',
      decisions: [
        {
          tenor: 'Annahme in Ausschussfassung',
          vote_kind: 'Namentliche Abstimmung',
          result: '308:190:71',
          majority: null,
        },
      ],
    },
  ],
};

describe('step details', () => {
  const section = procedureSection('2026-11-13', [VOTED]);
  if (section?.type !== 'timeline') throw new Error('timeline expected');
  const step = (label: string) => section.steps.find((s) => s.label === label);

  it('states the final vote from DIP, not an amendment', () => {
    expect(step('2./3. Lesung')?.facts).toBe(
      'Angenommen in der Fassung des Ausschusses: 308 Ja, 190 Nein, 71 Enthaltungen (namentliche Abstimmung). 2 Änderungsanträge wurden abgelehnt. Dazu wurde eine Entschließung angenommen.',
    );
  });

  it('says who introduced it, and where first', () => {
    expect(step('Eingebracht')?.facts).toBe(
      'Die Bundesregierung hat den Entwurf zuerst dem Bundesrat, dann dem Bundestag vorgelegt.',
    );
    expect(step('Eingebracht')?.links.map((l) => l.label)).toEqual([
      'Drucksache 453/26',
      'Drucksache 21/7868',
    ]);
  });

  it("carries the Bundestag Drucksache's summary", () => {
    expect(step('Eingebracht')?.summary).toBe(
      'Die Bundesregierung will das Verfassungsschutzgesetz neu fassen.',
    );
    expect(step('Ausschuss: Empfehlung')?.summary).toBe(
      'Der Innenausschuss empfiehlt Änderungen.',
    );
    expect(step('1. Lesung')?.summary).toBeNull();
  });

  it('asks about each step in the chat', () => {
    expect(step('1. Lesung')?.question).toBe(
      'Was wurde in der 1. Lesung am 24.09. gesagt?',
    );
    expect(step('1. Lesung')?.facts).toBe(
      'Erste Debatte im Bundestag. Danach wurde der Entwurf an die Ausschüsse überwiesen.',
    );
  });
});

describe('procedureMarker', () => {
  it("shows the law's dots and the item's step", () => {
    expect(procedureMarker('2026-11-13', [VOTED])).toEqual({
      tag: 'Gesetz',
      states: ['done', 'done', 'done', 'here', 'next'],
      step: '2./3. Lesung',
    });
  });

  it("falls back to the law's newest step, and to nothing for Anträge", () => {
    expect(procedureMarker('2026-10-01', [IN_COMMITTEE])?.step).toBe(
      'Ausschuss: Empfehlung',
    );
    expect(procedureMarker('2026-11-06', [motion('1')])).toBeNull();
  });
});

describe('edge cases from DIP', () => {
  const decision = (
    tenor: string,
    extra: Partial<StageDecision> = {},
  ): StageDecision => ({
    tenor,
    vote_kind: null,
    result: null,
    majority: null,
    ...extra,
  });

  it('reads a refusal as a refusal and expects nothing after it', () => {
    const refused = law('7', [
      ['2026-10-01', 'BT', 'Gesetzentwurf'],
      ['2026-10-20', 'BT', '2. Beratung'],
      ['2026-10-20', 'BT', '3. Beratung'],
      ['2026-11-06', 'BR', '2. Durchgang'],
    ]);
    refused.milestones[3] = {
      ...refused.milestones[3],
      decisions: [decision('Versagung der Zustimmung')],
    };
    const section = procedureSection('2026-10-20', [refused]);
    if (section?.type !== 'timeline') throw new Error('timeline expected');
    const br = section.steps.find((s) => s.label === 'Bundesrat: Entscheidung');
    expect(br?.facts).toBe('Der Bundesrat hat dem Gesetz nicht zugestimmt.');
    expect(section.steps.some((s) => s.state === 'next')).toBe(false);
  });

  it('names the Bundesrat once for its own bill', () => {
    const own = law(
      '8',
      [
        ['2026-06-01', 'BR', 'Gesetzentwurf'],
        ['2026-07-01', 'BT', 'Gesetzentwurf'],
      ],
      { initiative: ['Bundesrat'] },
    );
    const section = procedureSection('2026-07-01', [own]);
    if (section?.type !== 'timeline') throw new Error('timeline expected');
    expect(section.steps[0].facts).toBe(
      'Der Bundesrat hat den Entwurf beschlossen und dem Bundestag vorgelegt.',
    );
  });

  it('states a two-thirds majority and ignores a recommendation tenor', () => {
    const gg = law('9', [
      ['2025-03-10', 'BT', 'Gesetzentwurf'],
      ['2025-03-18', 'BT', '3. Beratung'],
    ]);
    gg.milestones[1] = {
      ...gg.milestones[1],
      decisions: [
        decision('Annahme der Beschlussempfehlung'),
        decision('Annahme in Ausschussfassung', {
          vote_kind: 'Namentliche Abstimmung',
          result: '512:206:0',
          majority: 'Zweidrittelmehrheit',
        }),
      ],
    };
    const section = procedureSection('2025-03-18', [gg]);
    if (section?.type !== 'timeline') throw new Error('timeline expected');
    expect(section.steps[1].facts).toBe(
      'Angenommen in der Fassung des Ausschusses mit Zweidrittelmehrheit: 512 Ja, 206 Nein, 0 Enthaltungen (namentliche Abstimmung).',
    );
  });

  it("takes the vote as the item's step when the committee reported that day", () => {
    const urgent = law('10', [
      ['2026-11-01', 'BT', 'Gesetzentwurf'],
      ['2026-11-12', 'BT', 'Beschlussempfehlung und Bericht'],
      ['2026-11-12', 'BT', '2. Beratung'],
      ['2026-11-12', 'BT', '3. Beratung'],
    ]);
    expect(procedureMarker('2026-11-12', [urgent])?.step).toBe('2./3. Lesung');
  });
});

describe('amendment votes', () => {
  it('tags the card with what was voted on', () => {
    expect(
      procedureMarker(
        '2026-11-13',
        [VOTED],
        'Neue Befugnisse des Verfassungsschutzes begrenzen (Änderungsantrag)',
      )?.tag,
    ).toBe('Änderungsantrag zum Gesetz');
    expect(
      procedureMarker(
        '2026-11-13',
        [VOTED],
        'Reform des Nachrichtendienstrechts',
      )?.tag,
    ).toBe('Gesetz');
  });
});

const party = (
  party_id: string,
  name: string,
  yes: number,
  no: number,
  abstain: number,
): DigestVoteParty => ({
  party_id,
  name,
  color: '#000',
  yes,
  no,
  abstain,
  no_show: 0,
});

describe('step feed links', () => {
  const vote = {
    id: 'bundestag_2026-11-13_v6771',
    kind: 'vote',
    date: '2026-11-13',
    rank: 1,
    region: 'DE',
    status: 'published',
    content: { de: { headline: 'Reform beschlossen' } },
    vote: {
      outcome: 'angenommen',
      parties: [
        party('cdu', 'CDU/CSU', 200, 0, 0),
        party('spd', 'SPD', 110, 2, 0),
        party('afd', 'AfD', 0, 140, 0),
        party('gruene', 'Die Grünen', 1, 0, 70),
        party('fraktionslos', 'Fraktionslos', 1, 1, 0),
      ],
    },
  } as unknown as FeedItem;
  const debate = {
    ...vote,
    id: 'bundestag_2026-11-13_d110-top4',
    kind: 'debate',
    rank: 2,
    content: { de: { headline: 'Streit um Befugnisse' } },
    vote: null,
  } as unknown as FeedItem;
  const step = (label: string, date: string | null): TimelineStep => ({
    date,
    label,
    state: 'done',
    facts: '',
    summary: null,
    links: [],
    question: '',
  });
  const href = (item: FeedItem) => `/?item=${item.id}`;

  it('names each Fraktion by how most of it voted', () => {
    expect(
      fractionLine((vote.vote as NonNullable<FeedItem['vote']>).parties),
    ).toBe('Ja: CDU/CSU, SPD · Nein: AfD · Enthalten: Die Grünen');
  });

  it('links the vote first, then the debate, never the item being read', () => {
    const links = stepFeedLinks(
      step('2./3. Lesung', '2026-11-13'),
      [debate, vote],
      'other',
      href,
    );
    expect(links.map((l) => l.kind)).toEqual(['Abstimmung', 'Debatte']);
    expect(links[0].detail).toBe(
      'Angenommen. Ja: CDU/CSU, SPD · Nein: AfD · Enthalten: Die Grünen',
    );
    expect(
      stepFeedLinks(
        step('2./3. Lesung', '2026-11-13'),
        [debate, vote],
        vote.id,
        href,
      ),
    ).toHaveLength(1);
  });

  it('links nothing for a step outside the plenary or another day', () => {
    expect(
      stepFeedLinks(
        step('Bundesrat: Entscheidung', '2026-11-13'),
        [vote],
        '',
        href,
      ),
    ).toEqual([]);
    expect(
      stepFeedLinks(step('1. Lesung', '2026-09-24'), [vote], '', href),
    ).toEqual([]);
    expect(
      stepFeedLinks(step('Bundesrat: Entscheidung', null), [vote], '', href),
    ).toEqual([]);
  });

  it('names the latest stage as the timeline does', () => {
    expect(plainStageName('3. Beratung')).toBe('2./3. Lesung');
    expect(plainStageName('1. Beratung')).toBe('1. Lesung');
    expect(plainStageName('2. Durchgang')).toBe('Bundesrat: Entscheidung');
    expect(plainStageName('Beschlussempfehlung und Bericht')).toBe(
      'Ausschuss: Empfehlung',
    );
  });

  it('carries the item to go back to', () => {
    expect(
      procedureChatHref('338341', 'Was?', 'bundestag_2026-11-13_v6771'),
    ).toBe(
      '/chat?procedure=338341&q=Was%3F&preset=ask&from=bundestag_2026-11-13_v6771',
    );
  });
});

describe('stepHref', () => {
  it('opens a protocol at its PDF page, not the printed one', () => {
    expect(
      stepHref('https://dserver.bundestag.de/btp/21/21089.pdf#P.13554', 42),
    ).toBe('https://dserver.bundestag.de/btp/21/21089.pdf#page=42');
  });
  it('opens the whole document without a page', () => {
    expect(
      stepHref('https://dserver.bundestag.de/btp/21/21089.pdf#P.13554', null),
    ).toBe('https://dserver.bundestag.de/btp/21/21089.pdf');
  });
});
