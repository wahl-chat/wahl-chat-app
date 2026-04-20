'use client';

import { cn } from '@/lib/utils';
import { SubtopicItem } from '@/modules/guided-exploration/components/navigation/subtopic-item';
import { TopicCard } from '@/modules/guided-exploration/components/navigation/topic-card';
import { ProgressIndicator } from '@/modules/guided-exploration/components/shared/progress-indicator';
import type {
  ExplorationNode,
  LeafSummary,
} from '@/modules/guided-exploration/types';
import {
  getBranchProgress,
  isLeaf,
} from '@/modules/guided-exploration/utils/tree-helpers';

interface BranchContentProps {
  node: ExplorationNode;
  summaries?: Record<string, LeafSummary> | null;
  onChildSelect: (nodeId: string) => void;
  className?: string;
}

export function BranchContent({
  node,
  summaries,
  onChildSelect,
  className,
}: BranchContentProps) {
  const progress = getBranchProgress(node);

  const getSummary = (childId: string): LeafSummary | null => {
    if (!summaries) return null;
    return summaries[childId] ?? null;
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Branch header */}
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">{node.name}</h1>
        <p className="text-foreground">{node.description}</p>
        <div className="pt-2">
          <ProgressIndicator
            explored={progress.explored}
            total={progress.total}
            variant="bar"
            showLabel
          />
        </div>
      </div>

      {/* Children list — mixed leaves and sub-branches render differently */}
      <ul
        className="flex list-none flex-col gap-4 pl-0"
        aria-label={`Unterthemen von ${node.name}`}
      >
        {node.children.map((child) => (
          <li key={child.id}>
            {isLeaf(child) ? (
              <SubtopicItem
                node={child}
                summary={getSummary(child.id)}
                onClick={() => onChildSelect(child.id)}
              />
            ) : (
              <TopicCard node={child} onClick={() => onChildSelect(child.id)} />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
