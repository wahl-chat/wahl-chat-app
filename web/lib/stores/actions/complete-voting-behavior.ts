import { addVotingBehaviorToMessage } from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const completeVotingBehavior: ChatStoreActionHandlerFor<
  'completeVotingBehavior'
> = (get, set) => async (requestId, votes, completeMessage) => {
  const { currentStreamedVotingBehavior, chatSessionId } = get();

  if (!chatSessionId) return;

  if (currentStreamedVotingBehavior?.requestId !== requestId) return;

  const { messages } = get();
  const indexOfGroupedMessage = messages.findIndex((m) =>
    m.messages.find((m) => m.id === requestId),
  );
  if (indexOfGroupedMessage === -1) return;

  const votingBehavior = {
    summary: completeMessage,
    votes,
  };

  set((state) => {
    const message = state.messages[indexOfGroupedMessage].messages.find(
      (m) => m.id === requestId,
    );

    if (!message) return;

    message.voting_behavior = votingBehavior;

    state.currentStreamedVotingBehavior = undefined;
    state.loading.votingBehaviorSummary = undefined;
  });

  await addVotingBehaviorToMessage(
    chatSessionId,
    messages[indexOfGroupedMessage].id,
    requestId,
    votingBehavior,
  );
};
