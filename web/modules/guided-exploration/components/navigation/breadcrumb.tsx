'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { BreadcrumbItem } from '@/modules/guided-exploration/types';
import { ChevronRight, MessageSquare } from 'lucide-react';
import Link from 'next/link';

interface ExplorationBreadcrumbProps {
  items: BreadcrumbItem[];
  chatUrl: string;
  onNavigate: (level: 'root' | 'topic' | 'subtopic', id?: string) => void;
  className?: string;
}

export function ExplorationBreadcrumb({
  items,
  chatUrl,
  onNavigate,
  className,
}: ExplorationBreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center', className)}>
      <ol className="flex items-center gap-1 text-sm">
        {/* Chat link */}
        <li>
          <Button variant="ghost" size="sm" asChild className="gap-1.5">
            <Link href={chatUrl}>
              <MessageSquare className="size-4" />
              <span className="sr-only md:not-sr-only">Chat</span>
            </Link>
          </Button>
        </li>

        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          const isClickable = !isLast;

          return (
            <li key={item.id} className="flex items-center gap-1">
              <ChevronRight
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
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
