'use client';

import DynamicRateLimitStickyInput from '@/components/dynamic-rate-limit-sticky-input';
import type {
  StickyInputAppearance,
  StickyInputDraftProps,
} from '@/components/sticky-input';
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

type Props = StickyInputDraftProps & {
  questions: ProposedQuestion[];
  className?: string;
  initialSystemStatus: LlmSystemStatus;
  hasValidServerUser?: boolean;
  contextId?: string;
  partyIds?: string[];
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
  value,
  onValueChange,
  focusRequest,
  partyIds,
}: Props) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [localDraft, setLocalDraft] = useState('');

  const pushLink = (question: string) => {
    if (!question.trim() || isLoading) return;

    setIsLoading(true);

    track('home_input_used', {
      question,
      context: contextId,
    });
    router.push(buildChatSessionUrl({ contextId, question, partyIds }));
  };

  return (
    <DynamicRateLimitStickyInput
      isLoading={isLoading}
      onSubmit={pushLink}
      quickReplies={questions.map((question) => question.content)}
      quickReplyTopics={Object.fromEntries(
        questions.map((question) => [question.content, question.topic]),
      )}
      initialSystemStatus={initialSystemStatus}
      hasValidServerUser={hasValidServerUser}
      className={cn('mt-4', className)}
      appearance={appearance}
      headerActions={headerActions}
      footerActions={footerActions}
      value={value ?? localDraft}
      onValueChange={onValueChange ?? setLocalDraft}
      focusRequest={focusRequest}
    />
  );
}

export default HomeInput;
