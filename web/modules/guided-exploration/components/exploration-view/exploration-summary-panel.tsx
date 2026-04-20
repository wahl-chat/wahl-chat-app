'use client';
import { cn } from '@/lib/utils';
import { LeafSummaryCard } from '@/modules/guided-exploration/components/shared/leaf-summary-card';
import type {
  ExplorationNode,
  ExplorationTree,
  LeafSummary,
} from '@/modules/guided-exploration/types';
import {
  getBranchProgress,
  isLeaf,
} from '@/modules/guided-exploration/utils/tree-helpers';

interface ExplorationSummaryPanelProps {
  tree: ExplorationTree;
  currentPath: string[];
  summaries: Record<string, LeafSummary> | null;
  onNavigate: (nodeId: string) => void;
  className?: string;
}

/**
 * Summary panel showing exploration progress with card-styled items.
 * Renders the recursive tree structure.
 */
export function ExplorationSummaryPanel({
  tree,
  currentPath,
  summaries,
  onNavigate,
  className,
}: ExplorationSummaryPanelProps) {
  const currentLeafId = currentPath[currentPath.length - 1];

  const getSummary = (nodeId: string): LeafSummary | null => {
    if (!summaries) return null;
    return summaries[nodeId] ?? null;
  };

  function renderNode(node: ExplorationNode) {
    if (isLeaf(node)) {
      return (
        <li key={node.id}>
          <LeafSummaryCard
            node={node}
            summary={getSummary(node.id)}
            isActive={node.id === currentLeafId}
            onNavigate={onNavigate}
          />
        </li>
      );
    }

    // Branch node
    const branchProgress = getBranchProgress(node);

    return (
      <li key={node.id}>
        <h3 className="mb-3 flex items-center justify-between font-medium">
          <span>{node.name}</span>
          <span className="text-sm text-foreground">
            {branchProgress.explored}/{branchProgress.total}
          </span>
        </h3>
        <ul className="flex flex-col gap-3">
          {node.children.map((child) => renderNode(child))}
        </ul>
      </li>
    );
  }

  return (
    <nav
      className={cn('flex h-full flex-col', className)}
      aria-label="Themenübersicht"
    >
      <div className="flex-1 overflow-y-auto p-4">
        <ul className="space-y-6">
          {tree.root.children.map((child) => renderNode(child))}
        </ul>
      </div>
    </nav>
  );
}
