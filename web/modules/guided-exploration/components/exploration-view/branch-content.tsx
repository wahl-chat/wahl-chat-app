'use client';

import { cn } from '@/lib/utils';
import { SubtopicItem } from '@/modules/guided-exploration/components/navigation/subtopic-item';
import { ProgressIndicator } from '@/modules/guided-exploration/components/shared/progress-indicator';
import type { LeafSummary, Topic } from '@/modules/guided-exploration/types';

interface BranchContentProps {
  topic: Topic;
  summaries?: Record<string, LeafSummary> | null;
  onSubtopicSelect: (subtopicId: string) => void;
  className?: string;
}

export function BranchContent({
  topic,
  summaries,
  onSubtopicSelect,
  className,
}: BranchContentProps) {
  const explored = topic.subtopics.filter(
    (s) => s.status === 'explored',
  ).length;
  const total = topic.subtopics.length;

  // Get summary for a subtopic
  const getSummary = (subtopicId: string): LeafSummary | null => {
    if (!summaries) return null;
    // Try compound ID first, then simple ID
    return (
      summaries[subtopicId] ?? summaries[`${topic.id}.${subtopicId}`] ?? null
    );
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Topic header */}
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">{topic.name}</h1>
        <p className="text-muted-foreground">{topic.description}</p>
        <div className="pt-2">
          <ProgressIndicator
            explored={explored}
            total={total}
            variant="bar"
            showLabel
          />
        </div>
      </div>

      {/* Subtopic list */}
      <div
        className="flex flex-col gap-4"
        role="list"
        aria-label={`Unterthemen von ${topic.name}`}
      >
        {topic.subtopics.map((subtopic) => {
          // Extract the simple subtopic ID for lookup
          const simpleId = subtopic.id.includes('.')
            ? subtopic.id.split('.')[1]
            : subtopic.id;

          return (
            <SubtopicItem
              key={subtopic.id}
              subtopic={subtopic}
              summary={getSummary(simpleId)}
              onClick={() => onSubtopicSelect(subtopic.id)}
            />
          );
        })}
      </div>
    </div>
  );
}
