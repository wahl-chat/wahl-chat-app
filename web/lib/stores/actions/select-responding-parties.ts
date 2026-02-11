import { WAHL_CHAT_PARTY_ID } from '@/lib/constants';
import { updateChatSession } from '@/lib/firebase/firebase';
import type { StreamingMessage } from '@/lib/socket.types';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { generateUuid } from '@/lib/utils';

export const selectRespondingParties: ChatStoreActionHandlerFor<
  'selectRespondingParties'
> = (get, set) => async (sessionId, partyIds) => {
  set((state) => {
    if (state.chatSessionId !== sessionId) return;

    if (!state.currentStreamingMessages) return;

    state.currentStreamingMessages.messages = Object.fromEntries(
      partyIds.map((partyId) => [
        partyId,
        {
          party_id: partyId,
          content: '',
          id: generateUuid(),
          role: 'assistant',
          sources: [],
        } satisfies StreamingMessage,
      ]),
    );

    state.currentStreamingMessages.responding_party_ids = partyIds;
  });

  const { partyIds: currentPartyIds } = get();

  const newPartyIds = partyIds.filter(
    (partyId) =>
      !currentPartyIds.has(partyId) && partyId !== WAHL_CHAT_PARTY_ID,
  );

  if (newPartyIds.length > 0) {
    await updateChatSession(sessionId, {
      party_ids: [...currentPartyIds, ...newPartyIds],
    });

    set((state) => {
      state.partyIds = new Set([...currentPartyIds, ...newPartyIds]);
    });
  }
};
