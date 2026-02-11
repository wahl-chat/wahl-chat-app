'use client';

import { useChatSessionParam } from '@/lib/hooks/use-chat-session-param';
import {
  captureProlificParams,
  getWahlChatSessionMessageCount,
} from '@/lib/prolific-study/prolific-metadata';
import { createChatStore } from '@/lib/stores/chat-store';
import type { ChatStore } from '@/lib/stores/chat-store.types';
import { useSearchParams } from 'next/navigation';
import {
  type ReactNode,
  createContext,
  useContext,
  useEffect,
  useRef,
} from 'react';
import { useStore } from 'zustand';

export type ChatStoreApi = ReturnType<typeof createChatStore>;

export const ChatStoreContext = createContext<ChatStoreApi | undefined>(
  undefined,
);

type Props = {
  children: ReactNode;
  contextId?: string;
};

export const ChatStoreProvider = ({ children, contextId }: Props) => {
  const sessionId = useChatSessionParam();
  const searchParams = useSearchParams();
  const storeRef = useRef<ChatStoreApi>(null);
  if (!storeRef.current) {
    storeRef.current = createChatStore({
      chatSessionId: sessionId,
      contextId,
    });
  }

  useEffect(() => {
    const metadata = captureProlificParams(searchParams);
    if (metadata && storeRef.current) {
      storeRef.current.getState().setProlificMetadata(metadata);
    }

    if (storeRef.current) {
      const count = getWahlChatSessionMessageCount();
      storeRef.current.getState().setProlificMessageCount(count);
    }
  }, []);

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
