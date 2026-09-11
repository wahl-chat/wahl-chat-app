'use client';

import DynamicRateLimitStickyInput from '@/components/dynamic-rate-limit-sticky-input';
import type { StickyInputAppearance } from '@/components/sticky-input';
import { buildChatSessionUrl } from '@/lib/chat-route';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import type {
  LlmSystemStatus,
  ProposedQuestion,
} from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { track } from '@vercel/analytics/react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

type Props = {
  questions: ProposedQuestion[];
  className?: string;
  initialSystemStatus: LlmSystemStatus;
  hasValidServerUser?: boolean;
  contextId?: string;
  appearance?: StickyInputAppearance;
  headerActions?: React.ReactNode;
  footerActions?: React.ReactNode;
};

function HomeInput({
  questions,
  className,
  initialSystemStatus,
  hasValidServerUser,
  contextId = DEFAULT_CONTEXT_ID,
  appearance,
  headerActions,
  footerActions,
}: Props) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const pushLink = (question: string) => {
    if (!question) return;

    setIsLoading(true);

    track('home_input_used', {
      question,
      context: contextId,
    });
    router.push(buildChatSessionUrl({ contextId, question }));
  };

  return (
    <DynamicRateLimitStickyInput
      isLoading={isLoading}
      onSubmit={pushLink}
      quickReplies={questions.map((question) => question.content)}
      initialSystemStatus={initialSystemStatus}
      hasValidServerUser={hasValidServerUser}
      className={cn('mt-4', className)}
      appearance={appearance}
      headerActions={headerActions}
      footerActions={footerActions}
    />
  );
}

export default HomeInput;
