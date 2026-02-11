import { scrollMessageBottomInView } from '@/lib/scroll-utils';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const generateVotingBehaviorSummary: ChatStoreActionHandlerFor<
  'generateVotingBehaviorSummary'
> = (get, set) => async (partyId, message) => {
  const { socket, messages, getLLMSize, isAnonymous } = get();

  if (!socket?.io?.connected) {
    return;
  }

  const indexOfVotingBehaviorMessage = messages.findIndex((m) =>
    m.messages.find((m) => m.id === message.id),
  );

  if (indexOfVotingBehaviorMessage === -1) return;

  const lastUserMessageBeforeVotingBehavior = messages
    .slice(0, indexOfVotingBehaviorMessage)
    .findLast((m) => m.role === 'user');

  if (!lastUserMessageBeforeVotingBehavior || !message.content) return;

  socket?.io?.generateVotingBehaviorSummary({
    request_id: message.id,
    party_id: partyId,
    last_user_message: lastUserMessageBeforeVotingBehavior.messages[0].content,
    last_assistant_message: message.content,
    summary_llm_size: getLLMSize(),
    user_is_logged_in: !isAnonymous,
  });

  set((state) => {
    state.loading.votingBehaviorSummary = message.id;
    state.currentStreamedVotingBehavior = {
      requestId: message.id,
    };
    state.clickedVotingBehaviorSummaryButton = true;
  });

  await new Promise((resolve) => setTimeout(resolve, 10));

  scrollMessageBottomInView(message.id);
};
