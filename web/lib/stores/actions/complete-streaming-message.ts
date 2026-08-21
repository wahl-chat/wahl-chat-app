import { addMessageToGroupedMessageOfChatSession } from '@/lib/firebase/firebase';
import type { StreamingMessage } from '@/lib/socket.types';
import type {
  ChatStoreActionHandlerFor,
  GroupedMessage,
  MessageItem,
} from '@/lib/stores/chat-store.types';
import { generateUuid } from '@/lib/utils';
import { Timestamp } from 'firebase/firestore';

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

type FinalizeGet = Parameters<
  ChatStoreActionHandlerFor<'completeStreamingMessage'>
>[0];
type FinalizeSet = Parameters<
  ChatStoreActionHandlerFor<'completeStreamingMessage'>
>[1];

// Shared terminal step for a party turn: once EVERY announced responder is
// done (chunking_complete — success or failed), persist the successful
// answers as one grouped message and clear the streaming state. Failed
// responders are dropped here — their fallback text is never serialized as a
// normal assistant answer. loading.newMessage deliberately stays TRUE:
// party_complete is party-scoped, not turn-terminal (the backend may still be
// generating quick replies / title) — the turn is released by the
// quick_replies event or the stream's onFinish, so a second send can never
// race the still-active useChat request.
export const finalizeStreamingMessagesIfComplete = (
  get: FinalizeGet,
  set: FinalizeSet,
): void => {
  const current = get().currentStreamingMessages;
  if (!current) return;

  const allMessages = Object.values(current.messages);
  if (
    allMessages.length === 0 ||
    !allMessages.every((message) => message.chunking_complete)
  ) {
    return;
  }

  const survivors = allMessages.filter((message) => !message.failed);
  const safeGroupedMessageId = current.id ?? generateUuid();

  set((state) => {
    if (survivors.length > 0) {
      const newGroupedMessage: GroupedMessage = {
        id: safeGroupedMessageId,
        role: 'assistant',
        messages: survivors.map((message) => buildNewMessage(message)),
      };
      state.messages.push(newGroupedMessage);
    }
    state.currentStreamingMessages = undefined;
  });
};

export const completeStreamingMessage: ChatStoreActionHandlerFor<
  'completeStreamingMessage'
> = (get, set) => async (sessionId, partyId, completeMessage) => {
  const { currentStreamingMessages, chatSessionId } = get();

  if (!chatSessionId) return;
  if (chatSessionId !== sessionId) return;

  const currentStreamingMessage = currentStreamingMessages?.messages[partyId];

  if (!currentStreamingMessages || !currentStreamingMessage) return;

  set((state) => {
    if (!state.currentStreamingMessages) return;
    state.currentStreamingMessages.messages[partyId].chunking_complete = true;
    state.currentStreamingMessages.messages[partyId].content = completeMessage;
  });

  const safeGroupedMessageId = currentStreamingMessages.id ?? generateUuid();

  finalizeStreamingMessagesIfComplete(get, set);

  await addMessageToGroupedMessageOfChatSession(
    chatSessionId,
    safeGroupedMessageId,
    buildNewMessage(currentStreamingMessage, completeMessage),
  );
};
