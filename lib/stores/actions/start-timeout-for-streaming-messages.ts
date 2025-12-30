import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

const STREAMING_MESSAGE_TIMEOUT =
  Number(process.env.NEXT_PUBLIC_STREAMING_MESSAGE_TIMEOUT_MS) || 30000;
const STREAMING_MESSAGE_CHECK_INTERVAL = 500;
export const startTimeoutForStreamingMessages: ChatStoreActionHandlerFor<
  'startTimeoutForStreamingMessages'
> = (get, set) => async (streamingMessageId: string) => {
  const clearIntervalAndTimeout = () => {
    const { pendingStreamingMessageTimeoutHandler } = get();

    clearInterval(pendingStreamingMessageTimeoutHandler.interval);
    clearTimeout(pendingStreamingMessageTimeoutHandler.timeout);
  };

  const interval = setInterval(() => {
    const { currentStreamingMessages } = get();

    if (currentStreamingMessages?.id !== streamingMessageId) {
      clearIntervalAndTimeout();
    }
  }, STREAMING_MESSAGE_CHECK_INTERVAL);

  set((state) => {
    state.pendingStreamingMessageTimeoutHandler.interval = interval;
  });

  const timeout = setTimeout(() => {
    set((state) => {
      state.currentStreamingMessages = undefined;
      state.loading.newMessage = false;
    });

    get().cancelStreamingMessages(streamingMessageId);
  }, STREAMING_MESSAGE_TIMEOUT);

  set((state) => {
    state.pendingStreamingMessageTimeoutHandler.timeout = timeout;
  });
};
