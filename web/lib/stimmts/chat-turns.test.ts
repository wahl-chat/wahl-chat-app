import { describe, expect, it } from 'bun:test';
import type { ChatChip } from './chat-chips';
import {
  type ChatTurn,
  answerText,
  appendTurn,
  applyEvent,
  finishTurn,
  isStreaming,
  remainingChips,
  sourceNames,
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
