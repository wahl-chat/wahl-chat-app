'use client';

import DynamicRateLimitStickyInput from '@/components/dynamic-rate-limit-sticky-input';
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
};

function HomeInput({
  questions,
  className,
  initialSystemStatus,
  hasValidServerUser,
}: Props) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const pushLink = (question: string) => {
    if (!question) return;

    setIsLoading(true);

    track('home_input_used', {
      question,
    });
    router.push(`/session?q=${question}`);
  };

  return (
    <DynamicRateLimitStickyInput
      isLoading={isLoading}
      onSubmit={pushLink}
      quickReplies={questions.map((question) => question.content)}
      initialSystemStatus={initialSystemStatus}
      hasValidServerUser={hasValidServerUser}
      className={cn('mt-4', className)}
    />
  );
}

export default HomeInput;
