import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';
import { generateUuid } from '@/lib/utils';

export const initializeChatSession: ChatStoreActionHandlerFor<
  'initializeChatSession'
> = (get, set) => async () => {
  const {
    chatSessionId,
    contextId,
    socket,
    messages,
    currentChatTitle,
    partyIds,
    localPreliminaryChatSessionId,
    getLLMSize,
  } = get();

  if (!socket.io?.connected) {
    return;
  }

  if (!chatSessionId && !localPreliminaryChatSessionId) {
    set({
      localPreliminaryChatSessionId: generateUuid(),
    });
  }

  const chatHistory = messages.flatMap((message) =>
    message.messages.map((innerMessage) => ({
      ...innerMessage,
      role: innerMessage.role,
      created_at: message.created_at,
      quick_replies: message.quick_replies,
    })),
  );

  const lastQuickReplies = chatHistory.findLast(
    (message) => message.role === 'assistant',
  )?.quick_replies;

  socket.io.initializeChatSession({
    session_id:
      chatSessionId ?? get().localPreliminaryChatSessionId ?? generateUuid(),
    context_id: contextId ?? DEFAULT_CONTEXT_ID,
    party_ids: [...partyIds],
    chat_history: chatHistory,
    last_quick_replies: lastQuickReplies ?? [],
    current_title: currentChatTitle ?? [...partyIds].join(', ') ?? 'no-title',
    chat_response_llm_size: getLLMSize(),
  });
};
