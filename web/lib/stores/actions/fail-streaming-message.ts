import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { toast } from 'sonner';
import { finalizeStreamingMessagesIfComplete } from './complete-streaming-message';

// Terminal per-party FAILURE (party_complete with status.indicator "error"):
// the announced responder is done, but its fallback text must not be persisted
// or rendered as a normal assistant answer. Marks the responder failed +
// complete, surfaces the error, and finalizes the turn when every responder
// has terminated — in a mixed multi-party turn the successful answers still
// persist and no responder stays pending.
export const failStreamingMessage: ChatStoreActionHandlerFor<
  'failStreamingMessage'
> = (get, set) => (sessionId, partyId) => {
  const { currentStreamingMessages, chatSessionId } = get();

  if (!chatSessionId || chatSessionId !== sessionId) return;
  if (!currentStreamingMessages) return;

  toast.error('Eine Antwort konnte nicht geladen werden.');

  set((state) => {
    if (!state.currentStreamingMessages) return;
    const existing = state.currentStreamingMessages.messages[partyId];
    if (existing) {
      existing.chunking_complete = true;
      existing.failed = true;
    } else {
      // The responder errored before any chunk arrived — record a failed
      // placeholder so the all-complete check can terminate the turn.
      state.currentStreamingMessages.messages[partyId] = {
        id: `${partyId}-failed`,
        role: 'assistant',
        party_id: partyId,
        chunking_complete: true,
        failed: true,
      };
    }
  });

  finalizeStreamingMessagesIfComplete(get, set);
};
