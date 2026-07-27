import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

// Terminal turn release, called from the SSE stream's onFinish (and after
// terminal error events): party_complete is party-scoped, so the turn stays
// busy (loading.newMessage) until the stream itself has finished — enabling
// the input earlier lets a second sendMessage REPLACE the active useChat
// response and lose its trailing events (quick replies / title).
export const finishStreamingTurn: ChatStoreActionHandlerFor<
  'finishStreamingTurn'
> = (get, set) => () => {
  const { pendingStreamingMessageTimeoutHandler } = get();

  if (pendingStreamingMessageTimeoutHandler.timeout) {
    clearTimeout(pendingStreamingMessageTimeoutHandler.timeout);
  }

  set((state) => {
    state.loading.newMessage = false;
    state.pendingStreamingMessageTimeoutHandler.timeout = undefined;
  });
};
