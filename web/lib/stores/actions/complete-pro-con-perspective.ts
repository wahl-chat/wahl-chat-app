import { addProConPerspectiveToMessage } from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const completeProConPerspective: ChatStoreActionHandlerFor<
  'completeProConPerspective'
> = (get, set) => async (requestId, message) => {
  const { chatSessionId, messages } = get();

  if (!chatSessionId) return;

  const indexOfProConPerspectiveGroupedMessage = messages.findIndex((m) =>
    m.messages.find((m) => m.id === requestId),
  );
  if (indexOfProConPerspectiveGroupedMessage === -1) return;

  const indexOfProConPerspectiveMessage = messages[
    indexOfProConPerspectiveGroupedMessage
  ].messages.findIndex((m) => m.id === requestId);

  if (indexOfProConPerspectiveMessage === -1) return;

  set((state) => {
    state.messages[indexOfProConPerspectiveGroupedMessage].messages[
      indexOfProConPerspectiveMessage
    ].pro_con_perspective = message;
    state.loading.proConPerspective = undefined;
  });

  await addProConPerspectiveToMessage(
    chatSessionId,
    messages[indexOfProConPerspectiveGroupedMessage].id,
    requestId,
    message,
  );
};
