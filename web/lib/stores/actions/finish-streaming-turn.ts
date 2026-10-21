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

  // Study: count the answers this PARTICIPANT has completed, not this chat's.
  // The second answer is the questionnaire's primary trigger and the first
  // anchors the absolute fallback; both are cohort-blind (control symmetry).
  //
  // The count spans chats on purpose. Asking the second question in a fresh
  // chat is still a second question, but newChat empties `messages`, so a
  // per-chat count restarts at zero and the trigger never fires — which is
  // exactly what happened in testing.
  //
  // Counting grouped assistant messages is exactly "answers that landed":
  // finalizeStreamingMessagesIfComplete pushes nothing when every responder
  // failed, so an all-failed turn advances nothing.
  const {
    firstAnswerCompletedAt,
    secondAnswerCompletedAt,
    studyAnswersCompleted,
    sessionAnswersCounted,
    messages,
  } = get();

  const answersThisChat = messages.filter(
    (message) => message.role === 'assistant',
  ).length;
  if (answersThisChat <= sessionAnswersCounted) {
    return;
  }

  const completed =
    studyAnswersCompleted + (answersThisChat - sessionAnswersCounted);
  set({
    sessionAnswersCounted: answersThisChat,
    studyAnswersCompleted: completed,
  });

  // The stamp is per chat (it anchors this chat's fallback); the EVENT is per
  // participant, gated on the crossing, so a participant who arrives already
  // holding one answer does not log a second `first_answer_completed`.
  if (firstAnswerCompletedAt === undefined) {
    set({ firstAnswerCompletedAt: Date.now() });
  }
  if (studyAnswersCompleted < 1 && completed >= 1) {
    void get().recordStudyEvent('first_answer_completed');
  }
  if (secondAnswerCompletedAt === undefined && completed >= 2) {
    set({ secondAnswerCompletedAt: Date.now() });
  }
  if (studyAnswersCompleted < 2 && completed >= 2) {
    void get().recordStudyEvent('second_answer_completed');
  }
};
