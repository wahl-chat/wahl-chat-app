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

export const PENDING_VOICE_MESSAGE_KEY = 'pendingVoiceMessage';

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

  const handleVoiceMessage = (audioBytes: Uint8Array) => {
    setIsLoading(true);

    track('home_voice_input_used');

    // Store voice message in sessionStorage for the chat page to pick up
    // Convert to base64 since sessionStorage only accepts strings
    const base64 = btoa(String.fromCharCode(...audioBytes));
    sessionStorage.setItem(PENDING_VOICE_MESSAGE_KEY, base64);
    router.push('/session?voice=1');
  };

  return (
    <DynamicRateLimitStickyInput
      isLoading={isLoading}
      onSubmit={pushLink}
      onVoiceMessage={handleVoiceMessage}
      quickReplies={questions.map((question) => question.content)}
      initialSystemStatus={initialSystemStatus}
      hasValidServerUser={hasValidServerUser}
      className={cn('mt-4', className)}
    />
  );
}

export default HomeInput;
