import { updateMessageFeedback } from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setMessageFeedback: ChatStoreActionHandlerFor<
  'setMessageFeedback'
> = (get, set) => async (messageId, feedback) => {
  const { chatSessionId, messages } = get();
  if (!chatSessionId) return;

  const indexOfGroupedMessage = messages.findIndex((message) =>
    message.messages.some((m) => m.id === messageId),
  );

  if (indexOfGroupedMessage === -1) return;

  const indexOfMessageInGroup = messages[
    indexOfGroupedMessage
  ].messages.findIndex((m) => m.id === messageId);

  if (indexOfMessageInGroup === -1) return;

  set((state) => {
    state.messages[indexOfGroupedMessage].messages[
      indexOfMessageInGroup
    ].feedback = feedback;
  });

  const groupedMessageId = messages[indexOfGroupedMessage].id;

  await updateMessageFeedback(
    chatSessionId,
    groupedMessageId,
    messageId,
    feedback,
  );
};
