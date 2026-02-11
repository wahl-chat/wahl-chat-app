import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const addVotingBehaviorResult: ChatStoreActionHandlerFor<
  'addVotingBehaviorResult'
> = (get, set) => async (requestId, vote) => {
  const { currentStreamedVotingBehavior } = get();

  if (requestId !== currentStreamedVotingBehavior?.requestId) {
    return;
  }

  set((state) => {
    state.currentStreamedVotingBehavior = {
      ...state.currentStreamedVotingBehavior,
      requestId,
      votes: [...(state.currentStreamedVotingBehavior?.votes || []), vote],
    };
  });
};
