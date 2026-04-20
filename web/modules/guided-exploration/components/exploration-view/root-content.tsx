'use client';

import { cn } from '@/lib/utils';
import { SubtopicItem } from '@/modules/guided-exploration/components/navigation/subtopic-item';
import { TopicCard } from '@/modules/guided-exploration/components/navigation/topic-card';
import { ProgressIndicator } from '@/modules/guided-exploration/components/shared/progress-indicator';
import type { ExplorationTree } from '@/modules/guided-exploration/types';
import { getOverallProgress, isLeaf } from '@/modules/guided-exploration/utils';

interface RootContentProps {
  tree: ExplorationTree;
  onTopicSelect: (topicId: string) => void;
  className?: string;
}

export function RootContent({
  tree,
  onTopicSelect,
  className,
}: RootContentProps) {
  const progress = getOverallProgress(tree);

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Themen erkunden</h1>
        <p className="text-foreground">
          Wähle ein Thema aus, um die Positionen der Parteien zu vergleichen.
        </p>
        <div className="pt-2">
          <ProgressIndicator
            explored={progress.explored}
            total={progress.total}
            variant="bar"
            showLabel
          />
        </div>
      </div>

      {/* Single full-width column — keeps leaves and branches visually consistent,
          including mixed trees. */}
      <ul
        className="flex list-none flex-col gap-4"
        aria-label="Verfügbare Themen"
      >
        {tree.root.children.map((node) => (
          <li key={node.id}>
            {isLeaf(node) ? (
              <SubtopicItem
                node={node}
                onClick={() => onTopicSelect(node.id)}
              />
            ) : (
              <TopicCard node={node} onClick={() => onTopicSelect(node.id)} />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
