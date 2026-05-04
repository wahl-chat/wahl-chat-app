/**
 * useFirebaseSummaries Hook
 * Subscribes to Firebase for real-time summary updates, fanning out one
 * subscription per active exploration. Summaries land in the store under
 * `summaries[explorationId][leafId]` via `summaryActions.synced`.
 */

'use client';

import {
  type Unsubscribe,
  collection,
  onSnapshot,
  query,
} from 'firebase/firestore';
import { useEffect, useRef } from 'react';
import { useShallow } from 'zustand/react/shallow';

import { db } from '@/lib/firebase/firebase';
import {
  selectSessionId,
  selectTreeIds,
  summaryActions,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import type { LeafSummary } from '@/modules/guided-exploration/types';

export interface UseFirebaseSummariesReturn {
  /** Whether at least one subscription has yet to receive its first snapshot. */
  loading: boolean;
  /** All summaries keyed by [explorationId][leafId]. */
  summaries: Record<string, Record<string, LeafSummary>>;
}

/**
 * Hook that subscribes to Firebase for real-time summary updates,
 * one subscription per active exploration.
 */
export function useFirebaseSummaries(): UseFirebaseSummariesReturn {
  const dispatch = useExplorationStore((s) => s.dispatch);
  const sessionId = useExplorationStore(selectSessionId);
  const treeIds = useExplorationStore(useShallow(selectTreeIds));
  const summaries = useExplorationStore((s) => s.summaries.summaries);

  const loadingRef = useRef(true);
  const unsubscribesRef = useRef<Map<string, Unsubscribe>>(new Map());

  useEffect(() => {
    const subs = unsubscribesRef.current;

    // Tear down subs for explorations that are no longer active.
    for (const [eid, unsub] of subs) {
      if (!treeIds.includes(eid)) {
        unsub();
        subs.delete(eid);
      }
    }

    if (!sessionId || treeIds.length === 0) {
      loadingRef.current = false;
      return;
    }

    // Track per-exploration first-snapshot completion to compute `loading`.
    const pending = new Set<string>(treeIds.filter((eid) => !subs.has(eid)));
    if (pending.size > 0) loadingRef.current = true;

    for (const explorationId of treeIds) {
      if (subs.has(explorationId)) continue;

      const summariesRef = collection(
        db,
        'guided_exploration_sessions',
        sessionId,
        'explorations',
        explorationId,
        'summaries',
      );
      const summariesQuery = query(summariesRef);

      const unsub = onSnapshot(
        summariesQuery,
        (snapshot) => {
          const updated: Record<string, LeafSummary> = {};
          snapshot.docs.forEach((doc) => {
            const data = doc.data();
            if (data.nodeType === 'leaf') {
              updated[data.nodeId] = {
                leafId: data.nodeId,
                overview: data.summary ?? '',
                keyPoints: data.keyPoints ?? [],
                partyComparison: data.partyComparison,
                generatedAt: data.generatedAt?.toDate?.()?.toISOString() ?? '',
              };
            }
            if (data.isGenerating) {
              dispatch(summaryActions.generating(data.nodeId));
            }
          });
          dispatch(summaryActions.synced(explorationId, updated));
          pending.delete(explorationId);
          if (pending.size === 0) loadingRef.current = false;
        },
        (error) => {
          // Silently handle permission errors — summaries will come from SSE instead.
          if (error.code !== 'permission-denied') {
            console.error('Firebase summaries subscription error:', error);
          }
          pending.delete(explorationId);
          if (pending.size === 0) loadingRef.current = false;
        },
      );
      subs.set(explorationId, unsub);
    }
  }, [dispatch, sessionId, treeIds]);

  // Tear down all subscriptions on unmount.
  useEffect(() => {
    const subs = unsubscribesRef.current;
    return () => {
      for (const unsub of subs.values()) unsub();
      subs.clear();
    };
  }, []);

  return {
    loading: loadingRef.current,
    summaries,
  };
}
