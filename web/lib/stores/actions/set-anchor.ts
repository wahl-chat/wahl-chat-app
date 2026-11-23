import { isChatPageUrl } from '@/lib/chat-anchor';
import { updateChatSession } from '@/lib/firebase/firebase';
import type { ChatStoreActionHandlerFor } from '@/lib/stores/chat-store.types';

export const setAnchor: ChatStoreActionHandlerFor<'setAnchor'> =
  (get, set) => async (anchor) => {
    set({ anchor });

    const { chatSessionId, messages } = get();
    if (!chatSessionId || messages.length === 0) {
      // Until its first message a new chat's anchor lives in its URL.
      const url =
        typeof window !== 'undefined' ? new URL(window.location.href) : null;
      if (url && isChatPageUrl(url)) {
        url.searchParams.delete('feed_item');
        url.searchParams.delete('poll_id');
        url.searchParams.delete('procedure');
        if ('feed_item_id' in anchor) {
          url.searchParams.set('feed_item', anchor.feed_item_id);
        } else if ('vorgang_id' in anchor) {
          url.searchParams.set('procedure', anchor.vorgang_id);
        } else {
          url.searchParams.set('poll_id', String(anchor.poll_id));
        }
        window.history.replaceState(window.history.state, '', url);
      }
      return;
    }

    try {
      await updateChatSession(chatSessionId, { anchor });
    } catch (error) {
      console.error('Failed to store the chat anchor', error);
    }
  };
