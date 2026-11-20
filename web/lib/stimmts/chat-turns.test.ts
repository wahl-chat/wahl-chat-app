import { describe, expect, it } from 'bun:test';
import type { ChatChip } from './chat-chips';
import {
  type ChatTurn,
  answerText,
  appendTurn,
  applyEvent,
  citedSources,
  finishTurn,
  isStreaming,
  remainingChips,
  sourceNames,
  sourcePills,
  toggleTurn,
  turnHistory,
} from './chat-turns';

const turn = (overrides: Partial<ChatTurn> = {}): ChatTurn => ({
  id: 0,
  question: 'Warum?',
  answer: '',
  sources: [],
  status: 'streaming',
  open: true,
  ...overrides,
});

describe('appendTurn', () => {
  it('adds a streaming, open turn and folds every older one', () => {
    const turns = appendTurn(
      [turn({ id: 0, status: 'done', open: true })],
      1,
      '  Und dann?  ',
    );
    expect(turns).toEqual([
      turn({ id: 0, status: 'done', open: false }),
      turn({ id: 1, question: 'Und dann?' }),
    ]);
  });
});

describe('applyEvent', () => {
  it('appends text deltas', () => {
    const next = applyEvent(
      applyEvent(turn(), { kind: 'text', delta: 'Die ' }),
      { kind: 'text', delta: 'Grünen' },
    );
    expect(next.answer).toBe('Die Grünen');
  });

  it('replaces the sources, since a later list supersedes an earlier one', () => {
    const source = { label: 'A', url: 'https://a' };
    const next = applyEvent(
      applyEvent(turn(), { kind: 'sources', sources: [source] }),
      { kind: 'sources', sources: [] },
    );
    expect(next.sources).toEqual([]);
  });

  it('ends on done, taking the final text when it comes with one', () => {
    const streamed = turn({ answer: 'Entwurf [0]' });
    expect(applyEvent(streamed, { kind: 'done' })).toEqual(
      turn({ answer: 'Entwurf [0]', status: 'done' }),
    );
    expect(
      applyEvent(streamed, { kind: 'done', text: 'Final [1]' }).answer,
    ).toBe('Final [1]');
    expect(applyEvent(streamed, { kind: 'done', text: '' }).answer).toBe(
      'Entwurf [0]',
    );
  });

  it('ends on error', () => {
    expect(applyEvent(turn(), { kind: 'error' }).status).toBe('error');
  });

  it('ignores events after the turn ended', () => {
    const done = turn({ status: 'done', answer: 'Fertig' });
    expect(applyEvent(done, { kind: 'text', delta: ' mehr' })).toBe(done);
    expect(applyEvent(done, { kind: 'error' })).toBe(done);
  });
});

describe('citedSources', () => {
  // As the general chat lists them: 0-based places in its source list, some
  // dropped by the parser (no web link), so the places have gaps.
  const p0 = { label: 'Protokoll', url: 'https://p', index: 0 };
  const d2 = { label: 'Drucksache', url: 'https://d', index: 2 };
  const w3 = { label: 'Web', url: 'https://w', index: 3 };
  const v4 = { label: 'Video', url: 'https://v', index: 4 };

  it('keeps only cited sources, in source order as the general chat lists them', () => {
    expect(citedSources([p0, d2, w3, v4], 'Erst [4], dann [0, 2].')).toEqual([
      p0,
      d2,
      v4,
    ]);
  });

  it('skips a citation of a source the parser dropped, without shifting the others', () => {
    expect(citedSources([p0, d2, w3], 'Ohne Link [1], mit [2].')).toEqual([d2]);
  });

  it('shows no sources for an answer without citations', () => {
    expect(citedSources([p0, d2], 'Keine Quelle.')).toEqual([]);
  });

  it('keeps sources that carry no place, which are all meant to be shown', () => {
    const placeholder = { label: 'Abgeordnetenwatch', url: 'https://a' };
    expect(citedSources([placeholder], 'Kein Marker.')).toEqual([placeholder]);
  });
});

describe('applyEvent on done with listed sources', () => {
  const p0 = { label: 'Protokoll', url: 'https://p', index: 0 };
  const d1 = { label: 'Drucksache', url: 'https://d', index: 1 };

  it('narrows the sources to what the final answer cites', () => {
    const streamed = turn({ answer: 'Entwurf [0]', sources: [p0, d1] });
    expect(
      applyEvent(streamed, { kind: 'done', text: 'Final [1].' }).sources,
    ).toEqual([d1]);
    expect(applyEvent(streamed, { kind: 'done' }).sources).toEqual([p0]);
  });
});

describe('finishTurn', () => {
  it('turns a stream that stopped without an ending into an error', () => {
    expect(finishTurn(turn()).status).toBe('error');
  });

  it('leaves an ended turn as it is', () => {
    const done = turn({ status: 'done' });
    expect(finishTurn(done)).toBe(done);
  });
});

describe('toggleTurn', () => {
  it('opens and closes one turn only', () => {
    const turns = [turn({ id: 0, open: false }), turn({ id: 1, open: false })];
    const opened = toggleTurn(turns, 0);
    expect(opened.map((t) => t.open)).toEqual([true, false]);
    expect(toggleTurn(opened, 0).map((t) => t.open)).toEqual([false, false]);
  });
});

describe('isStreaming', () => {
  it('is true while any turn streams', () => {
    expect(isStreaming([])).toBe(false);
    expect(isStreaming([turn({ status: 'done' }), turn()])).toBe(true);
  });
});

describe('remainingChips', () => {
  const chips: ChatChip[] = [
    { label: 'A', question: 'Frage A?' },
    { label: 'B', question: 'Frage B?' },
  ];

  it('drops chips whose question was asked, however it ended', () => {
    expect(
      remainingChips(chips, [turn({ question: 'Frage A?', status: 'error' })]),
    ).toEqual([chips[1]]);
  });
});

describe('turnHistory', () => {
  it('sends answered turns only, before the current one', () => {
    expect(
      turnHistory([
        turn({ question: 'Eins', answer: 'A', status: 'done' }),
        turn({ question: 'Zwei', answer: 'halb', status: 'error' }),
        turn({ question: 'Drei', answer: '', status: 'done' }),
      ]),
    ).toEqual([{ question: 'Eins', answer: 'A' }]);
  });
});

describe('answerText', () => {
  it('drops citation markers, which the source pills stand for', () => {
    expect(answerText('Die Grünen lehnten ab [0, 2]. Die SPD [1] nicht.')).toBe(
      'Die Grünen lehnten ab. Die SPD nicht.',
    );
  });

  it('hides a marker that is still arriving', () => {
    expect(answerText('Die Grünen lehnten ab [1')).toBe(
      'Die Grünen lehnten ab',
    );
    expect(answerText('Die Grünen lehnten ab [')).toBe('Die Grünen lehnten ab');
  });

  it('keeps brackets that are not citations', () => {
    expect(answerText('Das Gesetz [BT-Drs.] gilt.')).toBe(
      'Das Gesetz [BT-Drs.] gilt.',
    );
  });
});

describe('sourceNames', () => {
  it('lists each label once, in order', () => {
    expect(
      sourceNames([
        { label: 'Plenarprotokoll', url: 'https://a' },
        { label: 'Abgeordnetenwatch', url: 'https://b' },
        { label: 'Plenarprotokoll', url: 'https://c' },
      ]),
    ).toBe('Plenarprotokoll · Abgeordnetenwatch');
  });
});

describe('sourcePills', () => {
  const a = { label: 'Drucksache 21/8157', url: 'https://a' };
  const b = { label: 'Abgeordnetenwatch', url: 'https://b' };

  it('names a single source on its pill, with no names line', () => {
    expect(sourcePills([a])).toEqual({
      pills: [{ text: a.label, label: a.label, url: a.url }],
      names: null,
    });
  });

  it('numbers several sources and names them on a line', () => {
    expect(sourcePills([a, b])).toEqual({
      pills: [
        { text: '1', label: `Quelle 1: ${a.label}`, url: a.url },
        { text: '2', label: `Quelle 2: ${b.label}`, url: b.url },
      ],
      names: 'Drucksache 21/8157 · Abgeordnetenwatch',
    });
  });

  it('has nothing to show without sources', () => {
    expect(sourcePills([])).toEqual({ pills: [], names: null });
  });
});
