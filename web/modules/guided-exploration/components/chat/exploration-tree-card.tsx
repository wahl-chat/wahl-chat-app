'use client';

import { ExplorationLeafCard } from '@/modules/guided-exploration/components/chat/exploration-leaf-card';
import { ExplorationOverviewCard } from '@/modules/guided-exploration/components/chat/exploration-overview-card';
import { ExplorationTopicCard } from '@/modules/guided-exploration/components/chat/exploration-topic-card';
import {
  selectOverview,
  selectTree,
  useExplorationStore,
} from '@/modules/guided-exploration/store';
import type {
  ExplorationNode,
  SessionMessage,
} from '@/modules/guided-exploration/types';
import {
  getPathTo,
  isLeaf,
} from '@/modules/guided-exploration/utils/tree-helpers';
import { Loader2 } from 'lucide-react';
import { useId, useMemo } from 'react';

interface ExplorationTreeCardProps {
  message: SessionMessage;
  onOpenLeaf?: (explorationId: string, leafId: string) => void;
  /**
   * If set, expands the ancestor chain so the deep-linked leaf becomes
   * visible without the user having to drill in manually.
   */
  deepLinkLeafId?: string | null;
}

/**
 * Renders an exploration as a chat-style message: an opener line followed
 * by a vertical stack of cards. Branch nodes are {@link ExplorationTopicCard}s
 * with controlled inline expand; leaves are {@link ExplorationLeafCard}s
 * that open the right-side leaf sidebar via {@link onOpenLeaf}.
 */
export function ExplorationTreeCard({
  message,
  onOpenLeaf,
  deepLinkLeafId,
}: ExplorationTreeCardProps) {
  const explorationId = message.explorationId ?? null;
  const tree = useExplorationStore(selectTree(explorationId));
  const overview = useExplorationStore(selectOverview(explorationId));
  const headingId = useId();
  const query = message.explorationQuery || message.content || '';

  const forceOpenIds = useMemo(() => {
    if (!tree || !deepLinkLeafId) return null;
    const path = getPathTo(tree, deepLinkLeafId);
    if (!path) return null;
    return new Set(path.map((n) => n.id));
  }, [tree, deepLinkLeafId]);

  if (!explorationId) return null;

  if (!tree) {
    return (
      <div className="flex items-center gap-3 py-1">
        <Loader2
          aria-hidden="true"
          className="size-4 shrink-0 animate-spin text-muted-foreground"
        />
        <p id={headingId} className="text-sm text-muted-foreground">
          Erkundung wird vorbereitet{query ? `: ${query}` : ''}…
        </p>
      </div>
    );
  }

  const root = tree.root;
  const handleOpen = onOpenLeaf
    ? (leafId: string) => onOpenLeaf(explorationId, leafId)
    : undefined;

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      {overview ? (
        <ExplorationOverviewCard overview={overview} headingId={headingId} />
      ) : (
        <p id={headingId} className="text-sm text-foreground">
          Hier sind die Themen, die ich für dich gefunden habe:
        </p>
      )}

      <ul
        className="flex list-none flex-col gap-2 pl-0"
        aria-label={`Themen zu: ${tree.originalQuery || query || root.name}`}
      >
        {root.children.map((child) => (
          <li key={child.id}>
            <TreeNode
              explorationId={explorationId}
              node={child}
              onOpenLeaf={handleOpen}
              forceOpenIds={forceOpenIds}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

interface TreeNodeProps {
  explorationId: string;
  node: ExplorationNode;
  onOpenLeaf?: (leafId: string) => void;
  forceOpenIds: Set<string> | null;
}

function TreeNode({
  explorationId,
  node,
  onOpenLeaf,
  forceOpenIds,
}: TreeNodeProps) {
  if (isLeaf(node)) {
    return <ExplorationLeafCard node={node} onOpen={onOpenLeaf} />;
  }

  return (
    <ExplorationTopicCard
      node={node}
      initialExpanded={forceOpenIds?.has(node.id) ?? false}
    >
      {node.children.map((child) => (
        <li key={child.id}>
          <TreeNode
            explorationId={explorationId}
            node={child}
            onOpenLeaf={onOpenLeaf}
            forceOpenIds={forceOpenIds}
          />
        </li>
      ))}
    </ExplorationTopicCard>
  );
}
