'use client';

import { useEffect, useState } from 'react';

import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type {
  ExplorationNode,
  ExplorationTree,
} from '@/modules/guided-exploration/types';

interface TopicTreePreviewProps {
  tree: ExplorationTree;
  thinkingMessage: string | null;
}

/** Animation delay between items in milliseconds */
const ITEM_DELAY_MS = 500;

/** Flatten the tree into an ordered list of (node, depth) for animation */
function flattenTree(
  node: ExplorationNode,
  depth = 0,
): Array<{ node: ExplorationNode; depth: number }> {
  const result: Array<{ node: ExplorationNode; depth: number }> = [];
  // Skip root node itself, start with children
  if (depth > 0) {
    result.push({ node, depth });
  }
  for (const child of node.children) {
    result.push(...flattenTree(child, depth + 1));
  }
  return result;
}

export function TopicTreePreview({
  tree,
  thinkingMessage,
}: TopicTreePreviewProps) {
  const [visibleCount, setVisibleCount] = useState(0);

  const flatItems = flattenTree(tree.root);
  const totalItems = flatItems.length;

  // Animate items appearing one by one
  useEffect(() => {
    if (visibleCount >= totalItems) return;

    const timer = setTimeout(() => {
      setVisibleCount((prev) => prev + 1);
    }, ITEM_DELAY_MS);

    return () => clearTimeout(timer);
  }, [visibleCount, totalItems]);

  return (
    <Card className="overflow-hidden">
      {/* Header with loading indicator */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="border-b bg-muted/50 px-4 py-3"
      >
        <div className="flex items-center gap-3">
          <div aria-hidden="true" className="relative size-4">
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
        <p className="mb-4 text-sm text-foreground">{tree.originalQuery}</p>

        <div className="space-y-1.5">
          {flatItems.map((item, index) => {
            const isVisible = index < visibleCount;
            const isBranch = item.node.children.length > 0;
            const indent = (item.depth - 1) * 24; // 24px per depth level

            return (
              <div
                key={item.node.id}
                className={cn(
                  'transition-all duration-500',
                  isVisible ? 'opacity-100' : 'opacity-0',
                )}
                style={{ marginLeft: `${indent}px` }}
              >
                {isVisible ? (
                  <div className="flex items-center gap-2">
                    {isBranch ? (
                      <>
                        <div className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                          {item.node.children.length}
                        </div>
                        <span className="font-medium">{item.node.name}</span>
                      </>
                    ) : (
                      <>
                        <div className="size-1.5 rounded-full bg-muted-foreground/50" />
                        <span className="text-sm text-foreground">
                          {item.node.name}
                        </span>
                      </>
                    )}
                  </div>
                ) : (
                  <Skeleton
                    className={cn('h-5', isBranch ? 'w-48' : 'w-32')}
                    style={{ opacity: 0.5 }}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
