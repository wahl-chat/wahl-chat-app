import { GENERAL_CONTEXT_ID, WAHL_CHAT_PARTY_ID } from '@/lib/constants';
import type { Puzzle } from './types';

export type ChatAnswerSource = {
  label: string;
  url: string;
  /**
   * The source's 0-based place in the general chat's own list, which its
   * "[n]" markers name. Kept because unusable entries are dropped, so a
   * source's place in this list is not its citation number. Absent when the
   * answer has no citation markers and every source is meant to be shown.
   */
  index?: number;
};

export type ChatAnswerEvent =
  | { kind: 'text'; delta: string }
  | { kind: 'sources'; sources: ChatAnswerSource[] }
  /**
   * `text` is the answer as finally checked, when the source sends one: the
   * general chat re-points or drops citations after streaming, so it can
   * differ from the streamed words and replaces them.
   */
  | { kind: 'done'; text?: string }
  | { kind: 'error' };

export type ChatTurnRequest = {
  puzzle: Puzzle;
  /** One per card: the general chat keys a conversation by it. */
  sessionId: string;
  question: string;
  /** Earlier answered turns of this card, oldest first. */
  history: { question: string; answer: string }[];
};

export type AnswerStream = (
  request: ChatTurnRequest,
  signal: AbortSignal,
) => AsyncIterable<ChatAnswerEvent>;

const PLACEHOLDER_SENTENCE =
  'Hier antwortet bald wahl.chat: kurz, in zwei bis drei Sätzen, mit Quellen aus Plenarprotokoll oder Drucksache.';

/**
 * Stands in for the general chat: words arrive one by one like a streamed
 * answer, so every state of the card can be tried locally without the
 * backend. Nothing leaves the device.
 */
export function createPlaceholderAnswer(delayMs: number): AnswerStream {
  return async function* placeholder({ puzzle }, signal) {
    const words = PLACEHOLDER_SENTENCE.split(' ');
    for (const [i, word] of words.entries()) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      if (signal.aborted) return;
      yield { kind: 'text', delta: i === 0 ? word : ` ${word}` };
    }
    if (signal.aborted) return;
    yield {
      kind: 'sources',
      sources: [{ label: puzzle.source.label, url: puzzle.source.url }],
    };
    yield { kind: 'done' };
  };
}

export const placeholderAnswer: AnswerStream = createPlaceholderAnswer(70);

type ParsedPart = Record<string, unknown>;

const isRecord = (value: unknown): value is ParsedPart =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/**
 * Only web links: a source URL ends up in an href, and a `javascript:` one
 * would run on tap.
 */
function toSource(entry: unknown, index: number): ChatAnswerSource | null {
  if (!isRecord(entry)) return null;
  const { url, source, source_document } = entry;
  if (typeof url !== 'string' || !/^https?:\/\//i.test(url)) return null;
  const label =
    (typeof source === 'string' && source.trim()) ||
    (typeof source_document === 'string' && source_document.trim()) ||
    hostOf(url);
  return label ? { label, url, index } : null;
}

/** Empty for a link the browser cannot read, which then is not shown. */
function hostOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

/**
 * One named event of the general chat, the inner `data` of a
 * `data-chat_event` part. The words are read from `party_chunk`, as the
 * general chat's own client does: the `text-delta` parts carry the same
 * words again.
 */
function fromChatEvent(event: unknown): ChatAnswerEvent[] {
  if (!isRecord(event)) return [{ kind: 'error' }];
  switch (event.type) {
    case 'party_chunk': {
      const chunk = event.chunk_content;
      if (typeof chunk !== 'string') return [{ kind: 'error' }];
      return chunk ? [{ kind: 'text', delta: chunk }] : [];
    }
    case 'sources_ready': {
      if (!Array.isArray(event.sources)) return [{ kind: 'error' }];
      const sources = event.sources
        .map(toSource)
        .filter((source): source is ChatAnswerSource => source !== null);
      return [{ kind: 'sources', sources }];
    }
    case 'party_complete': {
      // An error completion carries a fallback apology, not an answer.
      const status = event.status;
      if (isRecord(status) && status.indicator === 'error') {
        return [{ kind: 'error' }];
      }
      const text = event.complete_message;
      return [
        typeof text === 'string' ? { kind: 'done', text } : { kind: 'done' },
      ];
    }
    case 'error':
      return [{ kind: 'error' }];
    default:
      // responding_parties, tool_status, anchor, quick_replies_title and any
      // later addition: nothing the card shows.
      return [];
  }
}

function fromLine(line: string): ChatAnswerEvent[] {
  // Blank lines end an SSE event, ":" lines are keep-alive pings, and the
  // other fields (event:, id:, retry:) carry nothing here.
  if (!line.startsWith('data:')) return [];
  const payload = line.slice('data:'.length).replace(/^ /, '');
  if (payload === '[DONE]') return [];
  let part: unknown;
  try {
    part = JSON.parse(payload);
  } catch {
    return [{ kind: 'error' }];
  }
  if (!isRecord(part) || typeof part.type !== 'string') {
    return [{ kind: 'error' }];
  }
  return part.type === 'data-chat_event' ? fromChatEvent(part.data) : [];
}

/**
 * The general chat's SSE lines as card events. Each payload is one JSON part
 * on one `data:` line, so lines map one by one. Never throws: anything it
 * cannot read becomes an error event.
 */
export function parseGeneralChatEvents(lines: string[]): ChatAnswerEvent[] {
  return lines.flatMap(fromLine);
}

/** The same mapping fed with raw text chunks as they arrive off the wire. */
export function createGeneralChatParser() {
  let buffer = '';
  return {
    push(chunk: string): ChatAnswerEvent[] {
      buffer += chunk;
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      return parseGeneralChatEvents(
        lines.map((line) => line.replace(/\r$/, '')),
      );
    },
    end(): ChatAnswerEvent[] {
      const rest = buffer.replace(/\r$/, '');
      buffer = '';
      return rest ? parseGeneralChatEvents([rest]) : [];
    },
  };
}

type GeneralChatDeps = {
  fetch?: typeof fetch;
  /** The Firebase ID token, as the general chat sends it; empty when signed out. */
  authHeader: () => Promise<Record<string, string>>;
};

/**
 * Asks the general chat through `/api/chat` with the body its own client
 * sends: the question as the last user message, the conversation so far
 * (current question included) as history, no party focus and no preset (the
 * chips are our own questions), anchored on the day's vote.
 */
export function createGeneralChatAnswer({
  fetch: fetchImpl = fetch,
  authHeader,
}: GeneralChatDeps): AnswerStream {
  return async function* generalChat(request, signal) {
    const { puzzle, sessionId, question, history } = request;
    const body = {
      messages: [{ role: 'user', parts: [{ type: 'text', text: question }] }],
      session_id: sessionId,
      context_id: GENERAL_CONTEXT_ID,
      party_ids: [],
      chat_history: [
        ...history.flatMap((turn) => [
          { role: 'user', content: turn.question },
          {
            role: 'assistant',
            content: turn.answer,
            party_id: WAHL_CHAT_PARTY_ID,
          },
        ]),
        { role: 'user', content: question },
      ],
      anchor: { poll_id: puzzle.pollId },
      language: 'de',
    };

    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    try {
      const response = await fetchImpl('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          ...(await authHeader()),
        },
        body: JSON.stringify(body),
        signal,
      });
      if (!response.ok || !response.body) {
        yield { kind: 'error' };
        return;
      }
      reader = response.body.getReader();
      const decoder = new TextDecoder();
      const parser = createGeneralChatParser();
      while (true) {
        const { done, value } = await reader.read();
        const events = done
          ? [...parser.push(decoder.decode()), ...parser.end()]
          : parser.push(decoder.decode(value, { stream: true }));
        for (const event of events) {
          yield event;
          // The answer is complete here; what follows (suggested replies, a
          // title) is for the full chat, so the request ends early.
          if (event.kind === 'done' || event.kind === 'error') return;
        }
        if (done) break;
      }
      yield { kind: 'error' };
    } catch {
      if (!signal.aborted) yield { kind: 'error' };
    } finally {
      reader?.cancel().catch(() => {});
    }
  };
}

export const generalChatAnswer: AnswerStream = createGeneralChatAnswer({
  authHeader: async () => {
    const { getAuthHeader } = await import('@/lib/firebase/firebase');
    return getAuthHeader();
  },
});

type ChatAnswerMode = 'placeholder' | 'general-chat';

/**
 * Where the card's answers come from: the general chat behind `/api/chat`.
 * 'placeholder' is for trying the card without a backend; switching to it
 * needs STIMMTS_CHAT_ENABLED off for any real deployment (a test holds the
 * two together).
 */
export const CHAT_ANSWERS: ChatAnswerMode = 'general-chat';

const ANSWER_STREAMS: Record<ChatAnswerMode, AnswerStream> = {
  placeholder: placeholderAnswer,
  'general-chat': generalChatAnswer,
};

export const answerStream: AnswerStream = ANSWER_STREAMS[CHAT_ANSWERS];
