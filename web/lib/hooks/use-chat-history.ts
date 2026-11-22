'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { listenToHistory } from '@/lib/firebase/firebase';
import type { ChatSession } from '@/lib/firebase/firebase.types';
import { useEffect, useState } from 'react';

/** The user's recent chats across all contexts, newest first. */
export function useChatHistory(initialHistory?: ChatSession[]) {
  const { user } = useAnonymousAuth();
  const [history, setHistory] = useState<ChatSession[]>(initialHistory ?? []);

  useEffect(() => {
    if (!user?.uid) return;
    return listenToHistory(user.uid, setHistory);
  }, [user?.uid]);

  return history;
}
