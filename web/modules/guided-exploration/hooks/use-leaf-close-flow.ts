'use client';

import { useCallback, useRef, useState } from 'react';

import type { ExplorationNode } from '@/modules/guided-exploration/types';

export interface LeafCloseInfo {
  /** Bumped on every close so consumers can react to repeat closes. */
  key: number;
  /** Spoken status read by the parent's live region after the leaf closes. */
  announcement: string;
  /**
   * The leaf the user was just in. The parent returns focus to this leaf's
   * card so the user lands back where they started — on the card now showing
   * its updated status — rather than being sent off to a skip-link.
   */
  focusLeafId: string;
}

interface ActiveLeafRef {
  explorationId: string;
  leafId: string;
}

interface UseLeafCloseFlowParams {
  activeLeaf: ActiveLeafRef | null;
  activeLeafNode: ExplorationNode | null;
  openLeaf: (explorationId: string, leafId: string) => void;
  closeLeaf: () => void;
  markExplored: (explorationId: string, leafId: string) => void | Promise<void>;
}

export interface UseLeafCloseFlowReturn {
  closeInfo: LeafCloseInfo | null;
  /** Open wrapper that clears any stale close hint first. */
  handleOpenLeaf: (explorationId: string, leafId: string) => void;
  /** Plain close (X / overlay / escape / browser back). */
  handleClose: () => void;
  /** Mark the leaf explored, then close. */
  handleMarkExplored: () => void;
}

/**
 * Owns the "where am I now" feedback shown when a leaf sidebar closes: a live
 * announcement (explored vs. just closed) plus the id of the leaf card the
 * parent returns focus to, so the user lands back on the topic they were just
 * in. Lives in the parent because the sidebar — and its own live region —
 * unmount on close.
 */
export function useLeafCloseFlow({
  activeLeaf,
  activeLeafNode,
  openLeaf,
  closeLeaf,
  markExplored,
}: UseLeafCloseFlowParams): UseLeafCloseFlowReturn {
  const [closeInfo, setCloseInfo] = useState<LeafCloseInfo | null>(null);
  const keyRef = useRef(0);

  const buildInfo = useCallback(
    (exploredNow: boolean): LeafCloseInfo => {
      keyRef.current += 1;
      // No leaf name here — focus lands back on the card first, which already
      // speaks the name. This only reports the action + where the user is now.
      const status = exploredNow ? 'Als erkundet markiert.' : 'Geschlossen.';
      return {
        key: keyRef.current,
        announcement: `${status} Zurück in der Themenübersicht.`,
        focusLeafId: activeLeaf?.leafId ?? '',
      };
    },
    [activeLeaf],
  );

  const handleClose = useCallback(() => {
    const explored = activeLeafNode?.status === 'explored';
    setCloseInfo(buildInfo(explored));
    closeLeaf();
  }, [activeLeafNode, buildInfo, closeLeaf]);

  const handleMarkExplored = useCallback(() => {
    if (!activeLeaf) return;
    void markExplored(activeLeaf.explorationId, activeLeaf.leafId);
    setCloseInfo(buildInfo(true));
    closeLeaf();
  }, [activeLeaf, buildInfo, closeLeaf, markExplored]);

  const handleOpenLeaf = useCallback(
    (explorationId: string, leafId: string) => {
      setCloseInfo(null);
      openLeaf(explorationId, leafId);
    },
    [openLeaf],
  );

  return { closeInfo, handleOpenLeaf, handleClose, handleMarkExplored };
}
