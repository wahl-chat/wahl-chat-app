'use client';

import { listenToSystemStatus } from '@/lib/firebase/firebase';
import type { LlmSystemStatus } from '@/lib/firebase/firebase.types';
import { useEffect, useState } from 'react';
import { useAnonymousAuth } from './anonymous-auth';
import StickyInput, { type StickyInputAppearance } from './sticky-input';
import StickyInputRateLimit from './sticky-input-rate-limit';

type Props = {
  isLoading: boolean;
  onSubmit: (message: string) => void;
  quickReplies?: string[];
  className?: string;
  initialSystemStatus: LlmSystemStatus;
  hasValidServerUser?: boolean;
  appearance?: StickyInputAppearance;
  headerActions?: React.ReactNode;
  footerActions?: React.ReactNode;
};

function DynamicRateLimitStickyInput({
  isLoading,
  onSubmit,
  quickReplies,
  className,
  initialSystemStatus,
  hasValidServerUser,
  appearance,
  headerActions,
  footerActions,
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
        appearance={appearance}
      />
    );
  }

  return (
    <StickyInput
      isLoading={isLoading}
      onSubmit={onSubmit}
      quickReplies={quickReplies}
      className={className}
      appearance={appearance}
      headerActions={headerActions}
      footerActions={footerActions}
    />
  );
}

export default DynamicRateLimitStickyInput;
