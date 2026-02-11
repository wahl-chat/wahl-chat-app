import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const addVotingBehaviorSummaryChunk: ChatStoreActionHandlerFor<
  'addVotingBehaviorSummaryChunk'
> = (get, set) => async (requestId, chunk) => {
  const { currentStreamedVotingBehavior } = get();

  if (currentStreamedVotingBehavior?.requestId !== requestId) return;

  set((state) => {
    state.currentStreamedVotingBehavior = {
      ...state.currentStreamedVotingBehavior,
      requestId,
      summary: (state.currentStreamedVotingBehavior?.summary || '') + chunk,
    };
  });
};
