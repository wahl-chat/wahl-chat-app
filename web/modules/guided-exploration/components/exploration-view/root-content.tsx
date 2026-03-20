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
  const hasOnlyLeaves = tree.root.children.every((n) => isLeaf(n));

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Themen erkunden</h1>
        <p className="text-muted-foreground">
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

      {/* Flat layout: all children are leaves */}
      {hasOnlyLeaves && (
        <div
          className="flex flex-col gap-4"
          role="list"
          aria-label="Verfügbare Themen"
        >
          {tree.root.children.map((node) => (
            <SubtopicItem
              key={node.id}
              node={node}
              onClick={() => onTopicSelect(node.id)}
            />
          ))}
        </div>
      )}

      {/* Nested layout: children are branches */}
      {!hasOnlyLeaves && (
        <div
          className="grid gap-4 sm:grid-cols-2"
          role="list"
          aria-label="Verfügbare Themen"
        >
          {tree.root.children.map((node) =>
            isLeaf(node) ? (
              <SubtopicItem
                key={node.id}
                node={node}
                onClick={() => onTopicSelect(node.id)}
              />
            ) : (
              <TopicCard
                key={node.id}
                node={node}
                onClick={() => onTopicSelect(node.id)}
              />
            ),
          )}
        </div>
      )}
    </div>
  );
}
