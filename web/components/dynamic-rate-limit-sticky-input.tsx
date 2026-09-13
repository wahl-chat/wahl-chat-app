'use client';

import LoginButton from '@/components/auth/login-button';
import { Button } from '@/components/ui/button';
import { listenToSystemStatus } from '@/lib/firebase/firebase';
import type { LlmSystemStatus } from '@/lib/firebase/firebase.types';
import { useEffect, useState } from 'react';
import { useAnonymousAuth } from './anonymous-auth';
import StickyInput, {
  type StickyInputDraftProps,
  type StickyInputAppearance,
} from './sticky-input';
import StickyInputRateLimit from './sticky-input-rate-limit';

type Props = StickyInputDraftProps & {
  isLoading: boolean;
  onSubmit: (message: string) => void;
  quickReplies?: string[];
  quickReplyTopics?: Record<string, string>;
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
  quickReplyTopics,
  className,
  initialSystemStatus,
  hasValidServerUser,
  appearance,
  headerActions,
  footerActions,
  value,
  onValueChange,
  focusRequest,
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

  if (!canAccessChatInput && appearance !== 'hero') {
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
      quickReplyTopics={quickReplyTopics}
      className={className}
      appearance={appearance}
      headerActions={headerActions}
      footerActions={footerActions}
      value={value}
      onValueChange={onValueChange}
      focusRequest={focusRequest}
      canSubmit={Boolean(
        canAccessChatInput || quickReplies?.includes(value ?? ''),
      )}
      notice={
        !canAccessChatInput && (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p>
              Der Server ist ausgelastet. Wähle eine Beispielfrage oder melde
              dich an. Dein Entwurf bleibt erhalten.
            </p>
            <LoginButton
              noUserChildren={
                <Button type="button" variant="secondary" size="sm">
                  Anmelden
                </Button>
              }
            />
          </div>
        )
      }
    />
  );
}

export default DynamicRateLimitStickyInput;
