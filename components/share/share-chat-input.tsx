'use client';
import { useAnonymousAuth } from '@/components/anonymous-auth';
import DynamicRateLimitStickyInput from '@/components/dynamic-rate-limit-sticky-input';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { copySharedChatSession } from '@/lib/firebase/firebase-admin';
import type { LlmSystemStatus } from '@/lib/firebase/firebase.types';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { toast } from 'sonner';

type Props = {
  snapshotId: string;
  contextId?: string;
  quickReplies?: string[];
  initialSystemStatus: LlmSystemStatus;
  hasValidServerUser?: boolean;
};

function ShareChatInput({
  snapshotId,
  contextId = DEFAULT_CONTEXT_ID,
  quickReplies,
  initialSystemStatus,
  hasValidServerUser,
}: Props) {
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();
  const { user } = useAnonymousAuth();

  const errorToast = () => {
    toast.error(
      'Es ist ein Fehler aufgetreten. Bitte versuche es erneut oder lade die Seite neu.',
    );
  };

  const handleStartChat = async (message: string) => {
    if (!user?.uid) {
      errorToast();
      return;
    }

    setIsLoading(true);

    try {
      const { session_id } = await copySharedChatSession(snapshotId, user.uid);

      const searchParams = new URLSearchParams({
        ref_snapshot_id: snapshotId,
        q: message,
      });

      router.push(
        `/${contextId}/session/${session_id}?${searchParams.toString()}`,
        {
          scroll: false,
        },
      );
    } catch (error) {
      console.error(error);
      errorToast();
      setIsLoading(false);
    }
  };

  return (
    <DynamicRateLimitStickyInput
      isLoading={isLoading}
      onSubmit={handleStartChat}
      quickReplies={quickReplies}
      initialSystemStatus={initialSystemStatus}
      hasValidServerUser={hasValidServerUser}
    />
  );
}

export default ShareChatInput;
