'use client';

import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { StatusDot } from '@/modules/guided-exploration/components/shared/status-dot';
import type {
  LeafSummary,
  TopicTree,
} from '@/modules/guided-exploration/types';
import { getOverallProgress } from '@/modules/guided-exploration/utils';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { nanoid } from 'nanoid';

interface ExplorationSummaryPanelProps {
  tree: TopicTree;
  currentPath: string[];
  summaries: Record<string, LeafSummary> | null;
  onNavigate: (topicId: string, subtopicId: string) => void;
  className?: string;
}

/**
 * Summary panel showing exploration progress with card-styled subtopic items.
 * Each item has an expandable summary and a navigate button.
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
  const currentSubtopicId = currentPath[1];

  const getSummary = (
    topicId: string,
    subtopicId: string,
  ): LeafSummary | null => {
    if (!summaries) return null;
    const simpleId = subtopicId.includes('.')
      ? subtopicId.split('.')[1]
      : subtopicId;
    return (
      summaries[simpleId] ??
      summaries[subtopicId] ??
      summaries[`${topicId}.${simpleId}`] ??
      null
    );
  };

  const isSubtopicActive = (topicId: string, subtopicId: string) => {
    return subtopicId === currentSubtopicId;
  };

  return (
    <nav
      className={cn('flex h-full flex-col', className)}
      aria-label="Themenübersicht"
    >
      {/* Progress header */}
      <header className="shrink-0 border-b p-4">
        <h2 className="mb-3 font-semibold">Fortschritt</h2>
        <div className="space-y-2">
          <Progress value={percentage} className="h-2" />
          <p className="text-sm text-muted-foreground">
            {progress.explored} von {progress.total} erkundet
          </p>
        </div>
      </header>

      {/* Topic list */}
      <div className="flex-1 overflow-y-auto p-4">
        <ul className="space-y-6">
          {tree.topics.map((topic) => {
            const topicExplored = topic.subtopics.filter(
              (s) => s.status === 'explored',
            ).length;
            const topicTotal = topic.subtopics.length;

            return (
              <li key={topic.id}>
                <h3 className="mb-3 flex items-center justify-between font-medium">
                  <span>{topic.name}</span>
                  <span className="text-sm text-muted-foreground">
                    {topicExplored}/{topicTotal}
                  </span>
                </h3>
                <ul className="flex flex-col gap-3">
                  {topic.subtopics.map((subtopic) => {
                    const isExplored = subtopic.status === 'explored';
                    const isActive = isSubtopicActive(topic.id, subtopic.id);
                    const summary = getSummary(topic.id, subtopic.id);

                    return (
                      <li key={subtopic.id}>
                        <article
                          className={cn(
                            'rounded-lg border bg-card shadow-sm transition-colors',
                            isActive && 'ring-2 ring-primary',
                          )}
                        >
                          {/* Card header */}
                          <div className="flex items-start gap-3 p-3">
                            <StatusDot
                              status={isExplored ? 'explored' : 'pending'}
                              className="mt-1 shrink-0"
                            />
                            <div className="min-w-0 flex-1">
                              <h4 className="text-sm font-medium leading-tight">
                                {subtopic.name}
                              </h4>
                              {!isExplored && (
                                <p className="mt-1 text-xs text-muted-foreground">
                                  Noch nicht erkundet
                                </p>
                              )}
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => onNavigate(topic.id, subtopic.id)}
                              className="shrink-0"
                              aria-label={`Zu "${subtopic.name}" navigieren`}
                            >
                              <ArrowRight className="size-4" />
                            </Button>
                          </div>

                          {/* Expandable summary */}
                          {isExplored && summary?.overview && (
                            <details className="group border-t">
                              <summary className="flex cursor-pointer items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:bg-muted/50">
                                <ChevronDown className="size-3 transition-transform group-open:rotate-180" />
                                Zusammenfassung
                              </summary>
                              <div className="px-3 pb-3 pt-1">
                                <p className="text-xs leading-relaxed text-muted-foreground">
                                  {summary.overview}
                                </p>
                                {summary.keyPoints &&
                                  summary.keyPoints.length > 0 && (
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
                  })}
                </ul>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
