'use client';

import { useEffect, useState } from 'react';

import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { TopicTree } from '@/modules/guided-exploration/types';

interface TopicTreePreviewProps {
  tree: TopicTree;
  thinkingMessage: string | null;
}

/** Animation delay between items in milliseconds */
const ITEM_DELAY_MS = 500;

export function TopicTreePreview({
  tree,
  thinkingMessage,
}: TopicTreePreviewProps) {
  const [visibleCount, setVisibleCount] = useState(0);

  // Calculate total items (topics + all subtopics)
  const allItems: Array<{
    type: 'topic' | 'subtopic';
    topicIndex: number;
    subtopicIndex?: number;
  }> = [];
  tree.topics.forEach((topic, topicIndex) => {
    allItems.push({ type: 'topic', topicIndex });
    topic.subtopics.forEach((_, subtopicIndex) => {
      allItems.push({ type: 'subtopic', topicIndex, subtopicIndex });
    });
  });

  const totalItems = allItems.length;

  // Animate items appearing one by one
  useEffect(() => {
    if (visibleCount >= totalItems) return;

    const timer = setTimeout(() => {
      setVisibleCount((prev) => prev + 1);
    }, ITEM_DELAY_MS);

    return () => clearTimeout(timer);
  }, [visibleCount, totalItems]);

  // Helper to check if an item should be visible
  const isItemVisible = (itemIndex: number) => visibleCount > itemIndex;

  // Get item index for a topic
  const getTopicItemIndex = (topicIndex: number) => {
    let index = 0;
    for (let i = 0; i < topicIndex; i++) {
      index += 1 + tree.topics[i].subtopics.length;
    }
    return index;
  };

  // Get item index for a subtopic
  const getSubtopicItemIndex = (topicIndex: number, subtopicIndex: number) => {
    return getTopicItemIndex(topicIndex) + 1 + subtopicIndex;
  };

  return (
    <Card className="overflow-hidden">
      {/* Header with loading indicator */}
      <div className="border-b bg-muted/50 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="relative size-4">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary/60 opacity-75" />
            <span className="relative inline-flex size-4 rounded-full bg-primary" />
          </div>
          <span className="text-sm font-medium">
            {thinkingMessage ?? 'Exploration wird vorbereitet...'}
          </span>
        </div>
      </div>

      {/* Tree content */}
      <div className="p-4">
        <p className="mb-4 text-sm text-muted-foreground">
          {tree.originalQuery}
        </p>

        <div className="space-y-4">
          {tree.topics.map((topic, topicIndex) => {
            const topicItemIndex = getTopicItemIndex(topicIndex);
            const isTopicVisible = isItemVisible(topicItemIndex);

            return (
              <div
                key={topic.id}
                className={cn(
                  'transition-all duration-500',
                  isTopicVisible ? 'opacity-100' : 'opacity-0',
                )}
              >
                {isTopicVisible ? (
                  <>
                    {/* Topic header */}
                    <div className="mb-2 flex items-center gap-2">
                      <div className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                        {topicIndex + 1}
                      </div>
                      <span className="font-medium">{topic.name}</span>
                    </div>

                    {/* Subtopics */}
                    <div className="ml-8 space-y-1.5">
                      {topic.subtopics.map((subtopic, subtopicIndex) => {
                        const subtopicItemIndex = getSubtopicItemIndex(
                          topicIndex,
                          subtopicIndex,
                        );
                        const isSubtopicVisible =
                          isItemVisible(subtopicItemIndex);

                        // Don't render anything for non-visible subtopics
                        // The skeleton block below handles placeholders
                        if (!isSubtopicVisible) return null;

                        return (
                          <div
                            key={subtopic.id}
                            className="flex items-center gap-2 text-sm text-muted-foreground transition-all duration-500"
                          >
                            <div className="size-1.5 rounded-full bg-muted-foreground/50" />
                            {subtopic.name}
                          </div>
                        );
                      })}

                      {/* Show skeleton for remaining subtopics not yet revealed */}
                      {topic.subtopics.length > 0 &&
                        !isItemVisible(
                          getSubtopicItemIndex(
                            topicIndex,
                            topic.subtopics.length - 1,
                          ),
                        ) && (
                          <div className="space-y-1.5">
                            {Array.from({
                              length: Math.max(
                                0,
                                topic.subtopics.length -
                                  Math.max(
                                    0,
                                    visibleCount -
                                      getTopicItemIndex(topicIndex) -
                                      1,
                                  ),
                              ),
                            }).map((_, i) => (
                              <Skeleton
                                key={`skeleton-${topic.id}-${i}`}
                                className="h-5 w-32"
                                style={{ opacity: 0.5 - i * 0.1 }}
                              />
                            ))}
                          </div>
                        )}
                    </div>
                  </>
                ) : (
                  /* Skeleton for topic not yet revealed */
                  <div className="space-y-2">
                    <Skeleton className="h-6 w-48" />
                    <div className="ml-8 space-y-1.5">
                      <Skeleton className="h-5 w-32" style={{ opacity: 0.5 }} />
                      <Skeleton className="h-5 w-28" style={{ opacity: 0.4 }} />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
