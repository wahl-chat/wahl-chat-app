'use client';

import { createContext, useContext } from 'react';

/** Where the chat is shown. On its own page a feed item opens in a preview
 * over the chat; in a sheet over the feed it opens in the feed itself. */
export type ChatHost =
  | { mode: 'page' }
  | {
      mode: 'sheet';
      /** Shows the item in the feed with the chat tucked away; false when
       * the feed has not loaded it. */
      openFeedItem: (feedItemId: string) => boolean;
    };

const ChatHostContext = createContext<ChatHost>({ mode: 'page' });

export const ChatHostProvider = ChatHostContext.Provider;

export function useChatHost(): ChatHost {
  return useContext(ChatHostContext);
}

/** Set when the feed hands a question to the chat page, so the way back can
 * return to the feed as it was. */
const FROM_FEED_KEY = 'wahlchat:chat-from-feed';

export function markFromFeed() {
  try {
    window.sessionStorage.setItem(FROM_FEED_KEY, '1');
  } catch {
    // Storage blocked: the way back links to the item instead.
  }
}

/** Whether this chat page was opened from the feed; reads the mark once,
 * so a later chat in the same tab does not inherit it. */
export function takeFromFeed(): boolean {
  try {
    const marked = window.sessionStorage.getItem(FROM_FEED_KEY) === '1';
    window.sessionStorage.removeItem(FROM_FEED_KEY);
    return marked;
  } catch {
    return false;
  }
}

/** The chat page a reader left to look at a feed item, so that item's
 * view can lead back. */
export type ReturnChat = { sessionId: string; label: string; itemId: string };

const RETURN_KEY = 'wahlchat:return-to-chat';

export function markReturnChat(chat: ReturnChat) {
  try {
    window.sessionStorage.setItem(RETURN_KEY, JSON.stringify(chat));
  } catch {
    // Storage blocked: Back still leads to the chat.
  }
}

export function readReturnChat(): ReturnChat | null {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(RETURN_KEY) ?? '');
    return typeof value?.sessionId === 'string' &&
      typeof value?.label === 'string' &&
      typeof value?.itemId === 'string'
      ? { sessionId: value.sessionId, label: value.label, itemId: value.itemId }
      : null;
  } catch {
    return null;
  }
}

export function clearReturnChat() {
  try {
    window.sessionStorage.removeItem(RETURN_KEY);
  } catch {
    // Nothing stored.
  }
}
