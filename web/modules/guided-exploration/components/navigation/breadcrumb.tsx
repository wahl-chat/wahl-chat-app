'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { BreadcrumbItem } from '@/modules/guided-exploration/types';
import { ChevronRight } from 'lucide-react';

interface ExplorationBreadcrumbProps {
  items: BreadcrumbItem[];
  /** @deprecated No longer used — tab bar handles chat navigation */
  chatUrl?: string;
  onNavigate: (level: 'root' | 'topic' | 'subtopic', id?: string) => void;
  className?: string;
}

export function ExplorationBreadcrumb({
  items,
  onNavigate,
  className,
}: ExplorationBreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center', className)}>
      <ol className="flex items-center gap-1 text-sm">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          const isFirst = index === 0;
          const isClickable = !isLast;

          return (
            <li key={item.id} className="flex items-center gap-1">
              {!isFirst && (
                <ChevronRight
                  className="size-4 text-muted-foreground"
                  aria-hidden="true"
                />
              )}
              {isClickable ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onNavigate(item.level, item.id)}
                >
                  {item.name}
                </Button>
              ) : (
                <span
                  className="px-3 py-1.5 font-medium text-foreground"
                  aria-current="page"
                >
                  {item.name}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
