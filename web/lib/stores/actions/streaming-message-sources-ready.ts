import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { generateUuid } from '@/lib/utils';

export const streamingMessageSourcesReady: ChatStoreActionHandlerFor<
  'streamingMessageSourcesReady'
> = (get, set) => (sessionId, partyId, sources) =>
  set((state) => {
    if (state.chatSessionId !== sessionId) return;

    if (!state.currentStreamingMessages) return;

    if (!state.currentStreamingMessages.messages[partyId]) {
      state.currentStreamingMessages.messages[partyId] = {
        party_id: partyId,
        content: '',
        id: generateUuid(),
        role: 'assistant',
        sources,
      };

      return;
    }

    state.currentStreamingMessages.messages[partyId].sources = sources;
  });
