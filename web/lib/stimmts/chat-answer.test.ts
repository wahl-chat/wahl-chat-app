import { describe, expect, it } from 'bun:test';
import {
  CHAT_ANSWERS,
  type ChatAnswerEvent,
  type ChatTurnRequest,
  createGeneralChatAnswer,
  createGeneralChatParser,
  createPlaceholderAnswer,
  parseGeneralChatEvents,
} from './chat-answer';
import { STIMMTS_CHAT_ENABLED } from './chat-chips';
import { FIXTURE_PUZZLES } from './fixtures';

const puzzle = FIXTURE_PUZZLES[0];

const request: ChatTurnRequest = {
  puzzle,
  sessionId: 'card-session',
  question: 'Warum Nein?',
  history: [],
};

async function collect(
  stream: AsyncIterable<ChatAnswerEvent>,
  until?: (events: ChatAnswerEvent[]) => void,
): Promise<ChatAnswerEvent[]> {
  const events: ChatAnswerEvent[] = [];
  for await (const event of stream) {
    events.push(event);
    until?.(events);
  }
  return events;
}

/** One SSE line as sse-starlette frames a payload. */
const data = (part: unknown) => `data: ${JSON.stringify(part)}`;
const chatEvent = (payload: unknown) =>
  data({ type: 'data-chat_event', data: payload });

/**
 * One whole turn, in the order the general chat's backend streams it:
 * message start, responding parties, tool status, sources, text deltas each
 * followed by the same text as a party chunk, the citation-checked complete
 * message, quick replies, finish.
 */
const TURN_LINES = [
  data({ type: 'start', messageId: 'm1' }),
  data({ type: 'start-step' }),
  chatEvent({
    type: 'responding_parties',
    session_id: 's',
    party_ids: ['wahl-chat'],
  }),
  chatEvent({
    type: 'tool_status',
    session_id: 's',
    call_id: 'anchor',
    tool: 'get_vote',
    label: 'Suche Abstimmung …',
    state: 'running',
  }),
  ': ping',
  chatEvent({
    type: 'sources_ready',
    session_id: 's',
    party_id: 'wahl-chat',
    rag_query: null,
    sources: [
      {
        source: 'Plenarprotokoll 21/30',
        page: 4,
        url: 'https://dserver.bundestag.de/btp/21/21030.pdf',
        source_document: 'Plenarprotokoll',
        document_publish_date: '2025-09-25',
      },
      {
        source: '',
        page: 0,
        url: 'https://www.abgeordnetenwatch.de/x',
        source_document: 'Abgeordnetenwatch',
        document_publish_date: '2025-09-25',
      },
      { source: 'Kaputt', page: 0, url: 'javascript:alert(1)' },
      { source: 'Ohne Link', page: 0 },
    ],
  }),
  data({ type: 'text-start', id: 't1' }),
  data({ type: 'text-delta', id: 't1', delta: 'Die Grünen ' }),
  chatEvent({
    type: 'party_chunk',
    session_id: 's',
    party_id: 'wahl-chat',
    chunk_content: 'Die Grünen ',
  }),
  data({ type: 'text-delta', id: 't1', delta: 'lehnten ab [0].' }),
  chatEvent({
    type: 'party_chunk',
    session_id: 's',
    party_id: 'wahl-chat',
    chunk_content: 'lehnten ab [0].',
  }),
  data({ type: 'text-end', id: 't1' }),
  chatEvent({
    type: 'party_complete',
    session_id: 's',
    party_id: 'wahl-chat',
    complete_message: 'Die Grünen lehnten ab [1].',
    message_id: 't1',
    status: { indicator: 'success', message: 'Success' },
  }),
  chatEvent({
    type: 'quick_replies_title',
    session_id: 's',
    quick_replies: ['Und die SPD?'],
    title: 'Titel',
  }),
  data({ type: 'finish-step' }),
  data({ type: 'finish' }),
  'data: [DONE]',
  '',
];

describe('placeholderAnswer', () => {
  const placeholder = createPlaceholderAnswer(0);

  it('streams a sentence word by word, then the puzzle source, then done', async () => {
    const events = await collect(
      placeholder(request, new AbortController().signal),
    );
    const texts = events.filter((event) => event.kind === 'text');
    expect(texts.length).toBeGreaterThan(5);
    const sentence = texts.map((event) => event.delta).join('');
    expect(sentence).toContain('wahl.chat');
    expect(sentence).not.toContain('  ');
    expect(events.at(-2)).toEqual({
      kind: 'sources',
      sources: [{ label: puzzle.source.label, url: puzzle.source.url }],
    });
    expect(events.at(-1)).toEqual({ kind: 'done' });
  });

  it('stops when the signal aborts', async () => {
    const controller = new AbortController();
    const events = await collect(
      placeholder(request, controller.signal),
      (so) => {
        if (so.length === 2) controller.abort();
      },
    );
    expect(events).toHaveLength(2);
    expect(events.every((event) => event.kind === 'text')).toBe(true);
  });

  it('yields nothing when already aborted', async () => {
    const controller = new AbortController();
    controller.abort();
    expect(await collect(placeholder(request, controller.signal))).toEqual([]);
  });
});

describe('CHAT_ANSWERS', () => {
  it('asks the general chat', () => {
    expect(CHAT_ANSWERS).toBe('general-chat');
  });
});

describe('parseGeneralChatEvents', () => {
  it('maps a whole turn: sources, party chunks as text, the checked answer on done', () => {
    expect(parseGeneralChatEvents(TURN_LINES)).toEqual([
      {
        kind: 'sources',
        sources: [
          {
            label: 'Plenarprotokoll 21/30',
            url: 'https://dserver.bundestag.de/btp/21/21030.pdf',
            index: 0,
          },
          {
            label: 'Abgeordnetenwatch',
            url: 'https://www.abgeordnetenwatch.de/x',
            index: 1,
          },
        ],
      },
      { kind: 'text', delta: 'Die Grünen ' },
      { kind: 'text', delta: 'lehnten ab [0].' },
      { kind: 'done', text: 'Die Grünen lehnten ab [1].' },
    ]);
  });

  it('counts text once: text-delta parts carry the same words as party_chunk', () => {
    const text = parseGeneralChatEvents(TURN_LINES)
      .filter((event) => event.kind === 'text')
      .map((event) => event.delta)
      .join('');
    expect(text).toBe('Die Grünen lehnten ab [0].');
  });

  it('maps an error party_complete to an error, not to its fallback text', () => {
    expect(
      parseGeneralChatEvents([
        chatEvent({
          type: 'party_complete',
          session_id: 's',
          party_id: 'wahl-chat',
          complete_message:
            'Es tut mir Leid, leider ist ein Fehler aufgetreten.',
          message_id: null,
          status: { indicator: 'error', message: 'x' },
        }),
      ]),
    ).toEqual([{ kind: 'error' }]);
  });

  it('maps a backend error part to an error', () => {
    expect(
      parseGeneralChatEvents([chatEvent({ type: 'error', message: 'x' })]),
    ).toEqual([{ kind: 'error' }]);
  });

  it('maps a done without a string message to a bare done', () => {
    expect(
      parseGeneralChatEvents([
        chatEvent({
          type: 'party_complete',
          status: { indicator: 'success', message: 'Success' },
        }),
      ]),
    ).toEqual([{ kind: 'done' }]);
  });

  it('keeps each source at its place in the chat list, skipping unusable ones', () => {
    expect(
      parseGeneralChatEvents([
        chatEvent({
          type: 'sources_ready',
          sources: [
            { source: 'Ohne Link', page: 0 },
            { source: '', source_document: '', url: 'https://' },
            { source: '', url: 'https://exa mple.de/x' },
            { source: 'Drucksache', url: 'https://dip.bundestag.de/d' },
          ],
        }),
      ]),
    ).toEqual([
      {
        kind: 'sources',
        sources: [
          { label: 'Drucksache', url: 'https://dip.bundestag.de/d', index: 3 },
        ],
      },
    ]);
  });

  it('turns malformed lines into an error and never throws', () => {
    const malformed = [
      'data: {not json',
      'data: 42',
      'data: null',
      data({ type: 'data-chat_event' }),
      data({ type: 'data-chat_event', data: 'x' }),
      chatEvent({ type: 'party_chunk', chunk_content: 7 }),
      chatEvent({ type: 'sources_ready', sources: 'x' }),
    ];
    for (const line of malformed) {
      expect(parseGeneralChatEvents([line])).toEqual([{ kind: 'error' }]);
    }
  });

  it('ignores comments, other SSE fields and unknown events', () => {
    expect(
      parseGeneralChatEvents([
        ': ping',
        'event: message',
        'id: 3',
        chatEvent({ type: 'anchor', anchor: { poll_id: 1 } }),
        chatEvent({ type: 'something_new' }),
        data({ type: 'reasoning-delta', delta: 'x' }),
      ]),
    ).toEqual([]);
  });
});

describe('createGeneralChatParser', () => {
  it('handles lines split across chunks and CRLF framing', () => {
    const parser = createGeneralChatParser();
    const wire = `${TURN_LINES.join('\r\n\r\n')}\r\n`;
    const events: ChatAnswerEvent[] = [];
    for (let i = 0; i < wire.length; i += 7) {
      events.push(...parser.push(wire.slice(i, i + 7)));
    }
    events.push(...parser.end());
    expect(events).toEqual(parseGeneralChatEvents(TURN_LINES));
  });

  it('flushes a last line without a newline on end', () => {
    const parser = createGeneralChatParser();
    expect(parser.push(chatEvent({ type: 'error' }))).toEqual([]);
    expect(parser.end()).toEqual([{ kind: 'error' }]);
  });
});

describe('generalChatAnswer', () => {
  type Call = { url: string; init: RequestInit };

  function sseResponse(lines: string[], status = 200): Response {
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const line of lines) {
          controller.enqueue(encoder.encode(`${line}\r\n\r\n`));
        }
        controller.close();
      },
    });
    return new Response(body, { status });
  }

  function answerWith(response: () => Response | Promise<Response>) {
    const calls: Call[] = [];
    const fetchImpl = async (
      url: string | URL | Request,
      init?: RequestInit,
    ) => {
      calls.push({ url: String(url), init: init ?? {} });
      return response();
    };
    const answer = createGeneralChatAnswer({
      fetch: fetchImpl as typeof fetch,
      authHeader: async () => ({ Authorization: 'Bearer test-token' }),
    });
    return { answer, calls };
  }

  it('posts what the general chat posts, anchored on the vote', async () => {
    const { answer, calls } = answerWith(() => sseResponse(TURN_LINES));
    await collect(
      answer(
        {
          puzzle,
          sessionId: 'card-session',
          question: 'Und die SPD?',
          history: [{ question: 'Warum Nein?', answer: 'Weil [0].' }],
        },
        new AbortController().signal,
      ),
    );
    expect(calls).toHaveLength(1);
    const [{ url, init }] = calls;
    expect(url).toBe('/api/chat');
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: 'Bearer test-token',
    });
    expect(JSON.parse(String(init.body))).toEqual({
      messages: [
        { role: 'user', parts: [{ type: 'text', text: 'Und die SPD?' }] },
      ],
      session_id: 'card-session',
      context_id: 'bundestag-aktuell',
      party_ids: [],
      chat_history: [
        { role: 'user', content: 'Warum Nein?' },
        { role: 'assistant', content: 'Weil [0].', party_id: 'wahl-chat' },
        { role: 'user', content: 'Und die SPD?' },
      ],
      anchor: { poll_id: puzzle.pollId },
      language: 'de',
    });
  });

  it('streams the mapped events and stops at done', async () => {
    const { answer } = answerWith(() => sseResponse(TURN_LINES));
    const events = await collect(answer(request, new AbortController().signal));
    expect(events).toEqual(parseGeneralChatEvents(TURN_LINES));
  });

  it('yields an error for a non-OK response', async () => {
    const { answer } = answerWith(() => new Response('nope', { status: 422 }));
    expect(
      await collect(answer(request, new AbortController().signal)),
    ).toEqual([{ kind: 'error' }]);
  });

  it('yields an error when the stream ends before the answer is complete', async () => {
    const { answer } = answerWith(() => sseResponse(TURN_LINES.slice(0, 8)));
    const events = await collect(answer(request, new AbortController().signal));
    expect(events.at(-1)).toEqual({ kind: 'error' });
  });

  it('yields an error when the network fails', async () => {
    const { answer } = answerWith(() => {
      throw new TypeError('Failed to fetch');
    });
    expect(
      await collect(answer(request, new AbortController().signal)),
    ).toEqual([{ kind: 'error' }]);
  });

  it('passes the signal to fetch and ends quietly once aborted', async () => {
    const controller = new AbortController();
    const { answer, calls } = answerWith(() => {
      controller.abort();
      throw new DOMException('aborted', 'AbortError');
    });
    expect(await collect(answer(request, controller.signal))).toEqual([]);
    expect(calls[0].init.signal).toBe(controller.signal);
  });
});

describe('the two chat switches', () => {
  it('are never on while the answers are still the placeholder', () => {
    expect(!STIMMTS_CHAT_ENABLED || CHAT_ANSWERS === 'general-chat').toBe(true);
  });
});
