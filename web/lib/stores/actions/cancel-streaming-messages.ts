import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const cancelStreamingMessages: ChatStoreActionHandlerFor<
  'cancelStreamingMessages'
> = (get, set) => async (streamingMessageId?: string) => {
  const { pendingStreamingMessageTimeoutHandler, currentStreamingMessages } =
    get();

  if (
    streamingMessageId &&
    currentStreamingMessages?.id !== streamingMessageId
  ) {
    return;
  }

  if (pendingStreamingMessageTimeoutHandler.interval) {
    clearInterval(pendingStreamingMessageTimeoutHandler.interval);
  }

  if (pendingStreamingMessageTimeoutHandler.timeout) {
    clearTimeout(pendingStreamingMessageTimeoutHandler.timeout);
  }

  set((state) => {
    state.currentStreamingMessages = undefined;
    state.loading.newMessage = false;
    state.pendingStreamingMessageTimeoutHandler.interval = undefined;
    state.pendingStreamingMessageTimeoutHandler.timeout = undefined;
  });
};
