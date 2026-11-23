'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { feedItemHref } from '@/lib/daily/share';
import { useRouter } from 'next/navigation';
import { useCallback } from 'react';
import { markReturnChat, useChatHost } from './chat-host';

/** Opens a feed item from the chat; the item's view then leads back. In
 * the sheet a loaded item opens under it instead. */
export function useLeaveForFeed() {
  const host = useChatHost();
  const router = useRouter();
  const sessionId = useChatStore((state) => state.chatSessionId);
  const title = useChatStore((state) => state.currentChatTitle);
  const question = useChatStore(
    (state) =>
      state.messages.find((group) => group.role === 'user')?.messages[0]
        ?.content,
  );

  const openItem = useCallback(
    (item: { id: string; region: string }) => {
      if (host.mode === 'sheet' && host.openFeedItem(item.id)) return;
      if (host.mode === 'page' && sessionId) {
        markReturnChat({
          sessionId,
          label: title || question || 'Dein Chat',
          itemId: item.id,
        });
      }
      router.push(feedItemHref(item.id, item.region));
    },
    [host, sessionId, title, question, router],
  );

  return { openItem };
}
