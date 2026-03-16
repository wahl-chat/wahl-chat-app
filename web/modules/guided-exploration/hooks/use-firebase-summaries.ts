/**
 * useFirebaseSummaries Hook
 * Subscribes to Firebase for real-time summary updates
 */

'use client';

import {
  type Unsubscribe,
  collection,
  onSnapshot,
  query,
} from 'firebase/firestore';
import { useEffect, useRef } from 'react';

import { db } from '@/lib/firebase/firebase';
import {
  selectExplorationId,
  selectSessionId,
  summaryActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import type { LeafSummary } from '@/modules/guided-exploration/types';

export interface UseFirebaseSummariesReturn {
  /** Whether summaries are currently loading */
  loading: boolean;
  /** Map of leafId to summary */
  summaries: Record<string, LeafSummary>;
}

/**
 * Hook that subscribes to Firebase for real-time summary updates
 */
export function useFirebaseSummaries(): UseFirebaseSummariesReturn {
  const dispatch = useExplorationStore((s) => s.dispatch);
  const sessionId = useExplorationStore(selectSessionId);
  const explorationId = useExplorationStore(selectExplorationId);
  const summaries = useExplorationStore((s) => s.summaries.summaries);

  const loadingRef = useRef(true);
  const unsubscribeRef = useRef<Unsubscribe | null>(null);

  useEffect(() => {
    // Clean up previous subscription
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }

    // Don't subscribe if we don't have session and exploration IDs
    if (!sessionId || !explorationId) {
      loadingRef.current = false;
      return;
    }

    loadingRef.current = true;

    // Path: /guided_exploration_sessions/{sessionId}/explorations/{explorationId}/summaries
    const summariesRef = collection(
      db,
      'guided_exploration_sessions',
      sessionId,
      'explorations',
      explorationId,
      'summaries',
    );

    const summariesQuery = query(summariesRef);

    unsubscribeRef.current = onSnapshot(
      summariesQuery,
      (snapshot) => {
        const updated: Record<string, LeafSummary> = {};

        snapshot.docs.forEach((doc) => {
          const data = doc.data();

          // Only include leaf summaries (not topic aggregates)
          if (data.nodeType === 'leaf') {
            updated[data.nodeId] = {
              leafId: data.nodeId,
              overview: data.summary ?? '',
              keyPoints: data.keyPoints ?? [],
              partyComparison: data.partyComparison,
              generatedAt: data.generatedAt?.toDate?.()?.toISOString() ?? '',
            };
          }

          // Track generating state
          if (data.isGenerating) {
            dispatch(summaryActions.generating(data.nodeId));
          }
        });

        dispatch(summaryActions.synced(updated));
        loadingRef.current = false;
      },
      (error) => {
        // Silently handle permission errors - summaries will come from SSE instead
        if (error.code !== 'permission-denied') {
          console.error('Firebase summaries subscription error:', error);
        }
        loadingRef.current = false;
      },
    );

    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
    };
  }, [dispatch, sessionId, explorationId]);

  return {
    loading: loadingRef.current,
    summaries,
  };
}
