'use client';

import type { LlmSystemStatus } from '@/lib/firebase/firebase.types';
import { useAnonymousAuth } from './anonymous-auth';
import StickyInput from './sticky-input';
import { useEffect, useState } from 'react';
import { listenToSystemStatus } from '@/lib/firebase/firebase';
import StickyInputRateLimit from './sticky-input-rate-limit';

type Props = {
  isLoading: boolean;
  onSubmit: (message: string) => void;
  quickReplies?: string[];
  className?: string;
  initialSystemStatus: LlmSystemStatus;
  hasValidServerUser?: boolean;
};

function DynamicRateLimitStickyInput({
  isLoading,
  onSubmit,
  quickReplies,
  className,
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
    return (
      <StickyInputRateLimit
        isLoading={isLoading}
        onSubmit={onSubmit}
        quickReplies={quickReplies}
        className={className}
      />
    );
  }

  return (
    <StickyInput
      isLoading={isLoading}
      onSubmit={onSubmit}
      quickReplies={quickReplies}
      className={className}
    />
  );
}

export default DynamicRateLimitStickyInput;
