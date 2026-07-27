import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { toast } from 'sonner';

// 60s default: the watchdog only resets on received `data-chat_event` parts, and
// the quiet gaps BEFORE `responding_parties` (retrieval) and AFTER the last
// `party_complete` (quick-replies/title generation) emit no events at all — 30s
// was not safely above their worst case.
const STREAMING_MESSAGE_TIMEOUT =
  Number(process.env.NEXT_PUBLIC_STREAMING_MESSAGE_TIMEOUT_MS) || 60000;

type WatchdogGet = Parameters<
  ChatStoreActionHandlerFor<'startTimeoutForStreamingMessages'>
>[0];
type WatchdogSet = Parameters<
  ChatStoreActionHandlerFor<'startTimeoutForStreamingMessages'>
>[1];

// Inactivity watchdog: arms (or re-arms) a single timeout bound to a specific
// streaming message id. V2 serializes multi-party answers over one SSE stream
// (backend budget 180s), so the deadline must be per-event inactivity, not a
// hard once-per-send cap — resetStreamingMessageWatchdog re-arms this on every
// received stream event.
const armStreamingMessageWatchdog = (
  get: WatchdogGet,
  set: WatchdogSet,
  streamingMessageId: string,
) => {
  const { pendingStreamingMessageTimeoutHandler } = get();

  // Clear any previously-armed watchdog before re-arming so at most one
  // timeout handle exists in the store at any time.
  if (pendingStreamingMessageTimeoutHandler.timeout) {
    clearTimeout(pendingStreamingMessageTimeoutHandler.timeout);
  }

  const timeout = setTimeout(() => {
    const { currentStreamingMessages } = get();

    // Stale-timer guard: a watchdog armed for a superseded message must no-op
    // so it can never wipe a newer message's stream.
    if (currentStreamingMessages?.id !== streamingMessageId) {
      return;
    }

    // Genuine inactivity: cancelStreamingMessages is the SINGLE cleanup path —
    // it aborts the live SSE stream (getSseChatStop) and wipes the streaming
    // state. It must run BEFORE any inline wipe so its id-guard
    // (currentStreamingMessages.id === streamingMessageId) still passes.
    get().cancelStreamingMessages(streamingMessageId);
    toast.error('Zeitüberschreitung — die Antwort wurde abgebrochen.');
  }, STREAMING_MESSAGE_TIMEOUT);

  set((state) => {
    state.pendingStreamingMessageTimeoutHandler.timeout = timeout;
  });
};

export const startTimeoutForStreamingMessages: ChatStoreActionHandlerFor<
  'startTimeoutForStreamingMessages'
> =
  (get, set) =>
  (streamingMessageId: string): void => {
    armStreamingMessageWatchdog(get, set, streamingMessageId);
  };

// Re-arms the watchdog for the currently streaming message. Called by the SSE
// provider on every received stream event so long multi-party streams are not
// wiped mid-flight; only true inactivity fires the watchdog.
export const resetStreamingMessageWatchdog: ChatStoreActionHandlerFor<
  'resetStreamingMessageWatchdog'
> = (get, set) => (): void => {
  const { currentStreamingMessages } = get();

  if (!currentStreamingMessages) {
    return;
  }

  armStreamingMessageWatchdog(get, set, currentStreamingMessages.id);
};
