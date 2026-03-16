'use client';

import { studyApi } from '@/modules/exploration-study/services/study-api';
import type { StudySession } from '@/modules/exploration-study/types';
import { getRouteForState } from '@/modules/exploration-study/utils';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';

export interface UseStudySessionOptions {
  sessionId: string;
  autoRedirect?: boolean;
}

export interface UseStudySessionReturn {
  session: StudySession | null;
  isLoading: boolean;
  error: string | null;
  refreshSession: () => Promise<void>;
}

export function useStudySession({
  sessionId,
  autoRedirect = true,
}: UseStudySessionOptions): UseStudySessionReturn {
  const [session, setSession] = useState<StudySession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const fetchSession = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    const response = await studyApi.getSession(sessionId);

    if (response.error) {
      setError(response.error);
      setSession(null);
    } else if (response.data) {
      setSession(response.data);

      // Redirect to the correct page based on session state
      if (autoRedirect) {
        const expectedPath = getRouteForState(sessionId, response.data.state);
        const currentPath = window.location.pathname;

        if (currentPath !== expectedPath) {
          router.replace(expectedPath);
        }
      }
    }

    setIsLoading(false);
  }, [sessionId, autoRedirect, router]);

  useEffect(() => {
    fetchSession();
  }, [fetchSession]);

  return {
    session,
    isLoading,
    error,
    refreshSession: fetchSession,
  };
}
