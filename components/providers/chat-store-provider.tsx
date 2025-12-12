'use client';

import { useChatSessionParam } from '@/lib/hooks/use-chat-session-param';
import { createChatStore } from '@/lib/stores/chat-store';
import type { ChatStore } from '@/lib/stores/chat-store.types';
import { type ReactNode, createContext, useContext, useRef } from 'react';
import { useStore } from 'zustand';

export type ChatStoreApi = ReturnType<typeof createChatStore>;

export const ChatStoreContext = createContext<ChatStoreApi | undefined>(
  undefined,
);

type Props = {
  children: ReactNode;
};

export const ChatStoreProvider = ({ children }: Props) => {
  const sessionId = useChatSessionParam();

  const storeRef = useRef<ChatStoreApi>(null);
  if (!storeRef.current) {
    storeRef.current = createChatStore({
      chatSessionId: sessionId,
    });
  }

  return (
    <ChatStoreContext.Provider value={storeRef.current}>
      {children}
    </ChatStoreContext.Provider>
  );
};

export const useChatStore = <T,>(selector: (store: ChatStore) => T): T => {
  const chatStoreContext = useContext(ChatStoreContext);

  if (!chatStoreContext) {
    throw new Error(`useChatStore must be used within ChatStoreProvider`);
  }

  return useStore(chatStoreContext, selector);
};
