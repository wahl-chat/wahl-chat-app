'use client';

import type { LlmSystemStatus } from '@/lib/firebase/firebase.types';
import ChatInputRateLimit from './chat-input-rate-limit';
import ChatInput from './chat-input';
import { useEffect, useState } from 'react';
import { useAnonymousAuth } from '@/components/anonymous-auth';
import { listenToSystemStatus } from '@/lib/firebase/firebase';

type Props = {
  initialSystemStatus: LlmSystemStatus;
  hasValidServerUser?: boolean;
};

function ChatDynamicChatInput({
  initialSystemStatus,
  hasValidServerUser,
}: Props) {
  const { user } = useAnonymousAuth();
  const [isAtRateLimit, setIsAtRateLimit] = useState(
    initialSystemStatus.is_at_rate_limit,
  );

  useEffect(() => {
    const unsubscribe = listenToSystemStatus((status) => {
      setIsAtRateLimit(status.is_at_rate_limit);
    });

    return unsubscribe;
  }, []);

  const isPriorityUser = user ? !user.isAnonymous : false;
  const canAccessChatInput =
    isPriorityUser || !isAtRateLimit || hasValidServerUser;

  if (!canAccessChatInput) {
    return <ChatInputRateLimit />;
  }

  return <ChatInput />;
}

export default ChatDynamicChatInput;
