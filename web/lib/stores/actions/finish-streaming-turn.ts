import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

// Terminal turn release, called from the SSE stream's onFinish (and after
// terminal error events): party_complete is party-scoped, so the turn stays
// busy (loading.newMessage) until the stream itself has finished — enabling
// the input earlier lets a second sendMessage REPLACE the active useChat
// response and lose its trailing events (quick replies / title).
export const finishStreamingTurn: ChatStoreActionHandlerFor<
  'finishStreamingTurn'
> = (get, set) => () => {
  const { pendingStreamingMessageTimeoutHandler } = get();

  if (pendingStreamingMessageTimeoutHandler.timeout) {
    clearTimeout(pendingStreamingMessageTimeoutHandler.timeout);
  }

  set((state) => {
    state.loading.newMessage = false;
    state.pendingStreamingMessageTimeoutHandler.timeout = undefined;
  });

  // Study: stamp the first TWO completed answers of the session. The second
  // is the questionnaire's primary trigger; the first anchors the absolute
  // fallback. Both stamps are cohort-blind — control symmetry.
  //
  // Counting grouped assistant messages is exactly "answers that landed":
  // finalizeStreamingMessagesIfComplete pushes nothing when every responder
  // failed, so an all-failed turn advances neither stamp. A whole-history
  // .some() cannot do this job — it is true on every turn after the first,
  // whatever that turn actually produced.
  const { firstAnswerCompletedAt, secondAnswerCompletedAt, messages } = get();
  const completedAnswers = messages.filter(
    (message) => message.role === 'assistant',
  ).length;

  if (firstAnswerCompletedAt === undefined && completedAnswers >= 1) {
    set({ firstAnswerCompletedAt: Date.now() });
    void get().recordStudyEvent('first_answer_completed');
  }
  if (secondAnswerCompletedAt === undefined && completedAnswers >= 2) {
    set({ secondAnswerCompletedAt: Date.now() });
    void get().recordStudyEvent('second_answer_completed');
  }
};
