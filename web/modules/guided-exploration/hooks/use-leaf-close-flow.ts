'use client';

import { useCallback, useRef, useState } from 'react';

import type {
  ExplorationNode,
  ExplorationTree,
} from '@/modules/guided-exploration/types';
import { getNextUnexploredLeaf } from '@/modules/guided-exploration/utils/tree-helpers';

export interface LeafCloseInfo {
  /** Bumped on every close so consumers can react to repeat closes. */
  key: number;
  /** Spoken status read by the parent's live region after the leaf closes. */
  announcement: string;
  /** Self-describing skip-link the parent focuses as the user's next step. */
  skip: { href: string; label: string };
}

interface ActiveLeafRef {
  explorationId: string;
  leafId: string;
}

interface UseLeafCloseFlowParams {
  trees: ExplorationTree[];
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
 * announcement (explored vs. just closed, plus the next topic or "all
 * explored") and a matching skip-link the parent focuses so the user has an
 * immediate next step. Lives in the parent because the sidebar — and its own
 * live region — unmount on close.
 */
export function useLeafCloseFlow({
  trees,
  activeLeaf,
  activeLeafNode,
  openLeaf,
  closeLeaf,
  markExplored,
}: UseLeafCloseFlowParams): UseLeafCloseFlowReturn {
  const [closeInfo, setCloseInfo] = useState<LeafCloseInfo | null>(null);
  const keyRef = useRef(0);

  const buildInfo = useCallback(
    (leafName: string, exploredNow: boolean): LeafCloseInfo => {
      const skipId = activeLeaf?.leafId;
      const pick = (node: ExplorationNode | undefined) =>
        node && node.id !== skipId ? { id: node.id, name: node.name } : null;

      // Prefer the next unexplored leaf in the leaf's own tree (continuing
      // from where the user was), then fall back to any other tree.
      let next: { id: string; name: string } | null = null;
      const currentTree = trees.find(
        (t) => t.explorationId === activeLeaf?.explorationId,
      );
      if (currentTree) next = pick(getNextUnexploredLeaf(currentTree, skipId));
      if (!next) {
        for (const t of trees) {
          if (t.explorationId === activeLeaf?.explorationId) continue;
          next = pick(getNextUnexploredLeaf(t));
          if (next) break;
        }
      }

      keyRef.current += 1;
      const status = exploredNow
        ? `„${leafName}“ als erkundet markiert.`
        : `„${leafName}“ geschlossen.`;

      if (next) {
        return {
          key: keyRef.current,
          announcement: `${status} Zurück in der Themenübersicht. Nächstes Thema: „${next.name}“.`,
          skip: {
            href: `#leaf-card-${next.id}`,
            label: `Zum nächsten Thema „${next.name}“ springen`,
          },
        };
      }
      return {
        key: keyRef.current,
        announcement: `${status} Zurück in der Themenübersicht. Alle Themen erkundet.`,
        skip: {
          href: '#chat-input',
          label: 'Alle Themen erkundet – zum Eingabefeld im Hauptchat springen',
        },
      };
    },
    [trees, activeLeaf],
  );

  const handleClose = useCallback(() => {
    const name = activeLeafNode?.name ?? 'Thema';
    const explored = activeLeafNode?.status === 'explored';
    setCloseInfo(buildInfo(name, explored));
    closeLeaf();
  }, [activeLeafNode, buildInfo, closeLeaf]);

  const handleMarkExplored = useCallback(() => {
    if (!activeLeaf) return;
    const name = activeLeafNode?.name ?? 'Thema';
    void markExplored(activeLeaf.explorationId, activeLeaf.leafId);
    setCloseInfo(buildInfo(name, true));
    closeLeaf();
  }, [activeLeaf, activeLeafNode, buildInfo, closeLeaf, markExplored]);

  const handleOpenLeaf = useCallback(
    (explorationId: string, leafId: string) => {
      setCloseInfo(null);
      openLeaf(explorationId, leafId);
    },
    [openLeaf],
  );

  return { closeInfo, handleOpenLeaf, handleClose, handleMarkExplored };
}
