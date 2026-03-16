'use client';

import { cn } from '@/lib/utils';
import { TopicCard } from '@/modules/guided-exploration/components/navigation/topic-card';
import { ProgressIndicator } from '@/modules/guided-exploration/components/shared/progress-indicator';
import type { TopicTree } from '@/modules/guided-exploration/types';
import { getOverallProgress } from '@/modules/guided-exploration/utils';

interface RootContentProps {
  tree: TopicTree;
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

      {/* Topic Grid */}
      <div
        className="grid gap-4 sm:grid-cols-2"
        role="list"
        aria-label="Verfügbare Themen"
      >
        {tree.topics.map((topic) => (
          <TopicCard
            key={topic.id}
            topic={topic}
            onClick={() => onTopicSelect(topic.id)}
          />
        ))}
      </div>
    </div>
  );
}
