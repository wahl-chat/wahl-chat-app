'use client';

import { cn } from '@/lib/utils';
import type { ChoicePromptEvent } from '@/modules/guided-exploration/types';
import { Compass, Zap } from 'lucide-react';
import { useId } from 'react';

interface ChoicePromptCardProps {
  choice: ChoicePromptEvent;
  onSubmit: (choice: 'summary' | 'explore') => void;
  isLoading: boolean;
}

export function ChoicePromptCard({
  choice,
  onSubmit,
  isLoading,
}: ChoicePromptCardProps) {
  const headingId = useId();
  const exploreOption = choice.options.find((o) => o.id === 'explore');
  const summaryOption = choice.options.find((o) => o.id === 'summary');

  return (
    <section aria-labelledby={headingId} className="space-y-3">
      {/* tabIndex={-1}: the chat view moves focus here when the prompt appears
          so arrival lands on a heading (announced as "Überschrift"). */}
      <h2
        id={headingId}
        tabIndex={-1}
        className="text-sm font-medium outline-none"
      >
        Wie möchtest du das Thema angehen?
      </h2>
      <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-stretch">
        {exploreOption && (
          <button
            type="button"
            onClick={() => onSubmit('explore')}
            disabled={isLoading}
            aria-describedby={headingId}
            className={cn(
              'group relative flex items-start gap-4 overflow-hidden rounded-lg border-2 border-primary/40 bg-primary/5 p-5 text-left shadow-sm transition-all hover:border-primary hover:bg-primary/10 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50',
            )}
          >
            <div
              className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground"
              aria-hidden="true"
            >
              <Compass className="size-6" />
            </div>
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <p className="text-base font-semibold">{exploreOption.label}</p>
                <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
                  Empfohlen
                </span>
              </div>
              <p className="text-sm text-foreground/80">
                {exploreOption.description}
              </p>
            </div>
          </button>
        )}
        {summaryOption && (
          <button
            type="button"
            onClick={() => onSubmit('summary')}
            disabled={isLoading}
            aria-describedby={headingId}
            className={cn(
              'flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-left text-sm text-muted-foreground transition-all hover:border-border hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 sm:flex-col sm:justify-center sm:px-4',
            )}
          >
            <Zap
              className="size-4 shrink-0 text-amber-500"
              aria-hidden="true"
            />
            <span className="font-medium">{summaryOption.label}</span>
          </button>
        )}
      </div>
    </section>
  );
}
