'use client';

import { cn } from '@/lib/utils';
import { ProgressIndicator } from '@/modules/guided-exploration/components/shared/progress-indicator';
import type { ExplorationNode } from '@/modules/guided-exploration/types';
import {
  getBranchProgress,
  isFullyExplored,
} from '@/modules/guided-exploration/utils/tree-helpers';

interface TopicCardProps {
  node: ExplorationNode;
  onClick: () => void;
  className?: string;
}

export function TopicCard({ node, onClick, className }: TopicCardProps) {
  const progress = getBranchProgress(node);
  const fullyExplored = isFullyExplored(node);

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`${node.name}, ${progress.explored} von ${progress.total} erkundet`}
      className={cn(
        'w-full rounded-lg border bg-card text-left shadow-sm transition-colors',
        'cursor-pointer hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className,
      )}
    >
      {/* Header */}
      <div className="flex flex-col space-y-1.5 p-6 pb-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-lg font-semibold leading-tight">{node.name}</h3>
          {fullyExplored && (
            <span className="shrink-0 rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              Fertig
            </span>
          )}
        </div>
      </div>
      {/* Content */}
      <div className="space-y-3 p-6 pt-0">
        <p className="line-clamp-2 text-sm text-muted-foreground">
          {node.description}
        </p>
        <ProgressIndicator
          explored={progress.explored}
          total={progress.total}
        />
      </div>
    </button>
  );
}
