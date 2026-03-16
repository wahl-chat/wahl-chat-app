'use client';

import { cn } from '@/lib/utils';
import { ProgressIndicator } from '@/modules/guided-exploration/components/shared/progress-indicator';
import type { Topic } from '@/modules/guided-exploration/types';

interface TopicCardProps {
  topic: Topic;
  onClick: () => void;
  className?: string;
}

export function TopicCard({ topic, onClick, className }: TopicCardProps) {
  const explored = topic.subtopics.filter(
    (s) => s.status === 'explored',
  ).length;
  const total = topic.subtopics.length;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`${topic.name}, ${explored} von ${total} erkundet`}
      className={cn(
        'w-full rounded-lg border bg-card text-left shadow-sm transition-colors',
        'cursor-pointer hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        className,
      )}
    >
      {/* Header */}
      <div className="flex flex-col space-y-1.5 p-6 pb-2">
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-lg font-semibold leading-tight">{topic.name}</h3>
          {topic.status === 'explored' && (
            <span className="shrink-0 rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              Fertig
            </span>
          )}
        </div>
      </div>
      {/* Content */}
      <div className="space-y-3 p-6 pt-0">
        <p className="line-clamp-2 text-sm text-muted-foreground">
          {topic.description}
        </p>
        <ProgressIndicator explored={explored} total={total} />
      </div>
    </button>
  );
}
