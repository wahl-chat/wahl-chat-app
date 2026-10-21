import { describe, expect, it, mock } from 'bun:test';
import type { PartyResponseChunkReadyPayload } from '@/lib/socket.types';
import type {
  ChatStore,
  CurrentStreamingMessages,
} from '@/lib/stores/chat-store.types';
import { produce } from 'immer';

mock.module('@/lib/firebase/firebase', () => ({
  addMessageToGroupedMessageOfChatSession: async () => {},
}));

const { mergeStreamingChunkPayloadForMessage } = await import(
  './merge-streaming-chunk-payload-for-message'
);
const { completeStreamingMessage } = await import(
  './complete-streaming-message'
);

const SESSION_ID = 'session-1';

function chunk(
  partyId: string,
  chunkContent: string,
): PartyResponseChunkReadyPayload {
  return {
    session_id: SESSION_ID,
    party_id: partyId,
    chunk_index: 0,
    chunk_content: chunkContent,
    is_end: false,
  };
}

function streamingTurn(): CurrentStreamingMessages {
  return {
    id: 'turn-1',
    responding_party_ids: ['spd', 'cdu'],
    messages: {
      spd: {
        id: 'msg-spd',
        role: 'assistant',
        party_id: 'spd',
        content: '',
        sources: [],
      },
      cdu: {
        id: 'msg-cdu',
        role: 'assistant',
        party_id: 'cdu',
        content: '',
        sources: [],
      },
    },
  };
}

function makeHarness() {
  let state = {
    chatSessionId: SESSION_ID,
    currentStreamingMessages: streamingTurn(),
    messages: [],
  } as unknown as ChatStore;

  const get = () => state;
  const set: Parameters<typeof mergeStreamingChunkPayloadForMessage>[1] = (
    updater,
  ) => {
    if (typeof updater === 'function') {
      state = produce(state, updater);
    } else {
      state = { ...state, ...updater };
    }
  };

  return {
    get,
    merge: mergeStreamingChunkPayloadForMessage(get, set),
    complete: completeStreamingMessage(get, set),
  };
}

describe('parallel multi-party streaming actions', () => {
  it('keeps interleaved party_chunk text intact per party', () => {
    const { get, merge } = makeHarness();

    merge(SESSION_ID, 'spd', chunk('spd', 'Klima'));
    merge(SESSION_ID, 'cdu', chunk('cdu', 'Tech'));
    merge(SESSION_ID, 'spd', chunk('spd', 'schutz'));
    merge(SESSION_ID, 'cdu', chunk('cdu', 'offen'));

    const messages = get().currentStreamingMessages?.messages;
    expect(messages?.spd.content).toBe('Klimaschutz');
    expect(messages?.cdu.content).toBe('Techoffen');
  });

  it('finalizes once on out-of-order party_complete in responding_parties order', async () => {
    const { get, complete } = makeHarness();

    await complete(SESSION_ID, 'cdu', 'CDU fertig');
    expect(get().currentStreamingMessages).toBeDefined();
    expect(get().messages).toHaveLength(0);

    await complete(SESSION_ID, 'spd', 'SPD fertig');
    expect(get().currentStreamingMessages).toBeUndefined();

    const grouped = get().messages;
    expect(grouped).toHaveLength(1);
    expect(grouped[0].messages.map((m) => m.party_id)).toEqual(['spd', 'cdu']);
    expect(grouped[0].messages.map((m) => m.content)).toEqual([
      'SPD fertig',
      'CDU fertig',
    ]);
  });
});
