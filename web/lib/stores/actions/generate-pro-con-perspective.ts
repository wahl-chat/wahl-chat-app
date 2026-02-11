import { scrollMessageBottomInView } from '@/lib/scroll-utils';
import type { StreamingMessage } from '@/lib/socket.types';
import type {
  ChatStoreActionHandlerFor,
  MessageItem,
} from '@/lib/stores/chat-store.types';
import { toast } from 'sonner';

export const generateProConPerspective: ChatStoreActionHandlerFor<
  'generateProConPerspective'
> =
  (get, set) =>
  async (partyId: string, message: MessageItem | StreamingMessage) => {
    const { chatSessionId, messages, socket } = get();

    if (!chatSessionId) return;

    if (!socket.io?.connected) {
      toast.error('Socket is not connected');

      return;
    }

    const indexOfProConPerspectiveMessage = messages.findIndex((m) =>
      m.messages.find((m) => m.id === message.id),
    );

    set((state) => {
      state.loading.proConPerspective = message.id;
      state.clickedProConButton = true;
    });

    if (indexOfProConPerspectiveMessage === -1) return;

    const lastUserMessageBeforeProConPerspective = messages
      .slice(0, indexOfProConPerspectiveMessage)
      .findLast((m) => m.role === 'user');

    if (!lastUserMessageBeforeProConPerspective || !message.content) return;

    socket.io?.generateProConPerspective({
      request_id: message.id,
      party_id: partyId,
      last_assistant_message: message.content,
      last_user_message:
        lastUserMessageBeforeProConPerspective.messages[0].content,
    });

    await new Promise((resolve) => setTimeout(resolve, 10));

    scrollMessageBottomInView(message.id);
  };
