import { getAuthHeader } from '@/lib/firebase/firebase';
import { scrollMessageBottomInView } from '@/lib/scroll-utils';
import type { Vote } from '@/lib/socket.types';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { toast } from 'sonner';

export const generateVotingBehaviorSummary: ChatStoreActionHandlerFor<
  'generateVotingBehaviorSummary'
> = (get, set) => async (partyId, message) => {
  const {
    messages,
    contextId,
    getLLMSize,
    addVotingBehaviorResult,
    addVotingBehaviorSummaryChunk,
    completeVotingBehavior,
  } = get();

  const indexOfVotingBehaviorMessage = messages.findIndex((m) =>
    m.messages.find((m) => m.id === message.id),
  );

  if (indexOfVotingBehaviorMessage === -1) return;

  const lastUserMessageBeforeVotingBehavior = messages
    .slice(0, indexOfVotingBehaviorMessage)
    .findLast((m) => m.role === 'user');

  if (!lastUserMessageBeforeVotingBehavior || !message.content) return;

  set((state) => {
    state.loading.votingBehaviorSummary = message.id;
    state.currentStreamedVotingBehavior = {
      requestId: message.id,
    };
    state.clickedVotingBehaviorSummaryButton = true;
  });

  try {
    const response = await fetch('/api/voting-behavior', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        // Firebase ID token when signed in ({} otherwise) — the proxy route
        // forwards it so the backend can verify auth claims.
        ...(await getAuthHeader()),
      },
      body: JSON.stringify({
        request_id: message.id,
        party_id: partyId,
        context_id: contextId,
        last_user_message:
          lastUserMessageBeforeVotingBehavior.messages[0].content,
        last_assistant_message: message.content,
        summary_llm_size: getLLMSize(),
      }),
    });

    if (!response.ok || !response.body) {
      throw new Error(`Voting behavior request failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    // Track whether the summary ever completed: the backend error path is
    // HTTP 200 + an `error` annotation, and a stream can also end without
    // `voting_behavior_complete` — both must clear the spinner
    // (loading.votingBehaviorSummary) and the half-populated
    // currentStreamedVotingBehavior.
    let receivedComplete = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        const payload = line.slice(5).trim();
        if (payload === '[DONE]') break;

        // v5 UI-message-stream: named app events ride inside data-chat_event
        // parts; the summary streams as text-delta parts. finish/finish-step
        // parts are ignored.
        let part: Record<string, unknown>;
        try {
          part = JSON.parse(payload) as Record<string, unknown>;
        } catch {
          continue; // malformed frame — skip
        }

        if (part.type === 'data-chat_event') {
          const annotation = part.data as Record<string, unknown>;
          if (annotation.type === 'vote_result') {
            addVotingBehaviorResult(
              annotation.request_id as string,
              annotation.vote as Vote,
              annotation.is_end as boolean,
            );
          } else if (annotation.type === 'voting_behavior_complete') {
            receivedComplete = true;
            completeVotingBehavior(
              annotation.request_id as string,
              annotation.votes as Vote[],
              annotation.message as string,
            );
          } else if (annotation.type === 'error') {
            console.error(
              '[voting-behavior] server error:',
              annotation.message,
            );
            toast.error('Fehler beim Laden des Abstimmungsverhaltens.');
            // Server-emitted error: stop the spinner and drop the
            // half-populated stream state (only `catch` cleared the spinner
            // before, so an HTTP-200 error left it spinning forever).
            set((state) => {
              state.loading.votingBehaviorSummary = undefined;
              state.currentStreamedVotingBehavior = undefined;
            });
          }
        } else if (part.type === 'text-delta') {
          // Summary text delta.
          addVotingBehaviorSummaryChunk(
            message.id,
            part.delta as string,
            false,
          );
        }
      }
    }

    // Stream ended without voting_behavior_complete (and without an explicit
    // error annotation): clear the spinner and the half-populated stream state.
    if (!receivedComplete) {
      set((state) => {
        state.loading.votingBehaviorSummary = undefined;
        state.currentStreamedVotingBehavior = undefined;
      });
    }
  } catch (error) {
    console.error('[generateVotingBehaviorSummary] error:', error);
    toast.error('Fehler beim Laden des Abstimmungsverhaltens.');

    set((state) => {
      state.loading.votingBehaviorSummary = undefined;
      state.currentStreamedVotingBehavior = undefined;
    });
    return;
  }

  await new Promise((resolve) => setTimeout(resolve, 10));

  scrollMessageBottomInView(message.id);
};
