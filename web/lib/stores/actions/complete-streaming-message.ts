import { addMessageToGroupedMessageOfChatSession } from '@/lib/firebase/firebase';
import type { StreamingMessage } from '@/lib/socket.types';
import type {
  ChatStoreActionHandlerFor,
  GroupedMessage,
  MessageItem,
} from '@/lib/stores/chat-store.types';
import { generateUuid } from '@/lib/utils';
import { Timestamp } from 'firebase/firestore';

export const completeStreamingMessage: ChatStoreActionHandlerFor<
  'completeStreamingMessage'
> = (get, set) => async (sessionId, partyId, completeMessage) => {
  const { currentStreamingMessages, chatSessionId } = get();

  if (!chatSessionId) return;
  // TODO: somehow store the message in firebase without knowing the current grouped message id
  if (chatSessionId !== sessionId) return;

  const currentStreamingMessage = currentStreamingMessages?.messages[partyId];

  if (!currentStreamingMessages || !currentStreamingMessage) return;

  set((state) => {
    if (!state.currentStreamingMessages) return;
    state.currentStreamingMessages.messages[partyId].chunking_complete = true;
    state.currentStreamingMessages.messages[partyId].content = completeMessage;
  });

  const buildNewMessage = (
    message: StreamingMessage,
    completeMessage?: string,
  ) => {
    return {
      id: message.id,
      content: completeMessage ?? message.content ?? '',
      sources: message.sources ?? [],
      party_id: message.party_id,
      created_at: Timestamp.now(),
      role: 'assistant',
    } satisfies MessageItem;
  };

  const safeGroupedMessageId = currentStreamingMessages.id ?? generateUuid();

  const updatedCurrentStreamingMessages = get().currentStreamingMessages;

  if (!updatedCurrentStreamingMessages) return;

  const allMessagesChunkingComplete = Object.values(
    updatedCurrentStreamingMessages.messages,
  ).every((message) => message.chunking_complete);

  if (allMessagesChunkingComplete) {
    set((state) => {
      const newGroupedMessage: GroupedMessage = {
        id: safeGroupedMessageId,
        role: 'assistant',
        messages: Object.values(updatedCurrentStreamingMessages.messages).map(
          (message) => buildNewMessage(message),
        ),
      };

      console.log('newGroupedMessage', newGroupedMessage);
      console.log(
        'responding_party_ids',
        updatedCurrentStreamingMessages.responding_party_ids,
      );

      state.messages.push(newGroupedMessage);
      state.currentStreamingMessages = undefined;
      state.loading.newMessage = false;
    });
  }

  await addMessageToGroupedMessageOfChatSession(
    chatSessionId,
    safeGroupedMessageId,
    buildNewMessage(currentStreamingMessage, completeMessage),
  );
};
