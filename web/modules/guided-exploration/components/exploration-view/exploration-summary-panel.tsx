'use client';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { StatusDot } from '@/modules/guided-exploration/components/shared/status-dot';
import type {
  ExplorationNode,
  ExplorationTree,
  LeafSummary,
} from '@/modules/guided-exploration/types';
import {
  getBranchProgress,
  getOverallProgress,
  isLeaf,
} from '@/modules/guided-exploration/utils/tree-helpers';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { nanoid } from 'nanoid';

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
  const progress = getOverallProgress(tree);
  const percentage =
    progress.total > 0
      ? Math.round((progress.explored / progress.total) * 100)
      : 0;
  const currentLeafId = currentPath[currentPath.length - 1];

  const getSummary = (nodeId: string): LeafSummary | null => {
    if (!summaries) return null;
    return summaries[nodeId] ?? null;
  };

  function renderNode(node: ExplorationNode) {
    if (isLeaf(node)) {
      const isExplored = node.status === 'explored';
      const isActive = node.id === currentLeafId;
      const summary = getSummary(node.id);

      return (
        <li key={node.id}>
          <article
            className={cn(
              'cursor-pointer rounded-lg border bg-card shadow-sm transition-colors hover:bg-accent',
              isActive && 'ring-2 ring-primary',
            )}
            onClick={() => onNavigate(node.id)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigate(node.id);
              }
            }}
            aria-label={`Zu "${node.name}" navigieren${isExplored ? ', erkundet' : ''}`}
          >
            <div className="flex items-start gap-3 p-3">
              <StatusDot
                status={isExplored ? 'explored' : 'pending'}
                className="mt-1 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-medium leading-tight">
                  {node.name}
                </h4>
                {!isExplored && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    Noch nicht erkundet
                  </p>
                )}
              </div>
              <ArrowRight className="mt-1 size-4 shrink-0 text-muted-foreground" />
            </div>

            {isExplored && summary?.overview && (
              <details
                className="group border-t"
                onClick={(e) => e.stopPropagation()}
                onKeyDown={(e) => e.stopPropagation()}
              >
                <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-muted/50">
                  <ChevronDown className="size-3 transition-transform group-open:rotate-180" />
                  Zusammenfassung
                </summary>
                <div className="px-3 pb-3 pt-1">
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {summary.overview}
                  </p>
                  {summary.keyPoints && summary.keyPoints.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {summary.keyPoints.map((point) => (
                        <li
                          key={nanoid()}
                          className="flex items-start gap-1.5 text-xs text-muted-foreground"
                        >
                          <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground/50" />
                          {point}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </details>
            )}
          </article>
        </li>
      );
    }

    // Branch node
    const branchProgress = getBranchProgress(node);

    return (
      <li key={node.id}>
        <h3 className="mb-3 flex items-center justify-between font-medium">
          <span>{node.name}</span>
          <span className="text-sm text-muted-foreground">
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
      <header className="shrink-0 border-b p-4">
        <h2 className="mb-3 font-semibold">Fortschritt</h2>
        <div className="space-y-2">
          <Progress value={percentage} className="h-2" />
          <p className="text-sm text-muted-foreground">
            {progress.explored} von {progress.total} erkundet
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-4">
        <ul className="space-y-6">
          {tree.root.children.map((child) => renderNode(child))}
        </ul>
      </div>
    </nav>
  );
}
