import { describe, expect, it } from 'bun:test';
import type { ToolStatus } from '@/lib/stores/chat-store.types';
import { upsertToolStatus } from './update-tool-status';

const running = (call_id: string, label: string): ToolStatus => ({
  call_id,
  tool: 'get_vote',
  label,
  state: 'running',
});

describe('upsertToolStatus', () => {
  it('adds new calls in order of their first event', () => {
    const lines = upsertToolStatus(
      upsertToolStatus([], running('a', 'Suche Abstimmung')),
      running('b', 'Suche Reden'),
    );
    expect(lines.map((l) => l.call_id)).toEqual(['a', 'b']);
  });

  it("updates a call's line in place when it is done", () => {
    const lines = upsertToolStatus(
      [running('a', 'Suche Abstimmung'), running('b', 'Suche Reden')],
      {
        call_id: 'a',
        tool: 'get_vote',
        label: 'Abstimmung nachgeschlagen',
        state: 'done',
      },
    );
    expect(lines).toEqual([
      {
        call_id: 'a',
        tool: 'get_vote',
        label: 'Abstimmung nachgeschlagen',
        state: 'done',
      },
      running('b', 'Suche Reden'),
    ]);
  });
});
