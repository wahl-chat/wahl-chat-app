import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { generateUuid } from '@/lib/utils';

// In the SSE model, there is no persistent socket connection to initialize.
// Session state is stateless: the client sends the full chat_history with
// each request (RESEARCH.md Open Question 3 resolution). This action becomes
// a no-op that only ensures a localPreliminaryChatSessionId is set.
export const initializeChatSession: ChatStoreActionHandlerFor<
  'initializeChatSession'
> = (get, set) => async () => {
  const { chatSessionId, localPreliminaryChatSessionId } = get();

  if (!chatSessionId && !localPreliminaryChatSessionId) {
    set({
      localPreliminaryChatSessionId: generateUuid(),
    });
  }

  // No explicit init event in the SSE model — session context is sent
  // per-request via the HTTP body in chatAddUserMessage (stateless SSE design).
};
