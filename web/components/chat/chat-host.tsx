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
