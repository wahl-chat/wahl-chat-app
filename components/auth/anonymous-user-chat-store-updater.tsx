'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { useEffect } from 'react';

function AnonymousUserChatStoreUpdater() {
  const { user } = useAnonymousAuth();
  const setIsAnonymous = useChatStore((state) => state.setIsAnonymous);

  useEffect(() => {
    if (user) {
      setIsAnonymous(user.isAnonymous);
    }
  }, [user, setIsAnonymous]);

  return null;
}

export default AnonymousUserChatStoreUpdater;
