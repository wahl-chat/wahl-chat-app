import { getSseChatStop } from '@/components/providers/sse-chat-provider';
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

  // Abort the live SSE HTTP stream so cancelled/timed-out streams actually
  // stop burning tokens instead of running to the proxy cap.
  getSseChatStop()?.();

  if (pendingStreamingMessageTimeoutHandler.timeout) {
    clearTimeout(pendingStreamingMessageTimeoutHandler.timeout);
  }

  set((state) => {
    state.currentStreamingMessages = undefined;
    state.loading.newMessage = false;
    state.pendingStreamingMessageTimeoutHandler.timeout = undefined;
  });
};
