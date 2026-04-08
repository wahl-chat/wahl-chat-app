'use client';

import { cn } from '@/lib/utils';
import type { ChoicePromptEvent } from '@/modules/guided-exploration/types';
import { Compass, Zap } from 'lucide-react';

interface ChoicePromptCardProps {
  choice: ChoicePromptEvent;
  onSubmit: (choice: 'summary' | 'explore') => void;
  isLoading: boolean;
}

const CHOICE_CONFIG = {
  summary: {
    icon: Zap,
    accent:
      'border-amber-500/30 hover:border-amber-500/50 hover:bg-amber-500/5',
    iconColor: 'text-amber-500',
  },
  explore: {
    icon: Compass,
    accent: 'border-primary/30 hover:border-primary/50 hover:bg-primary/5',
    iconColor: 'text-primary',
  },
} as const;

export function ChoicePromptCard({
  choice,
  onSubmit,
  isLoading,
}: ChoicePromptCardProps) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Wie möchtest du das Thema angehen?
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {choice.options.map((option) => {
          const config = CHOICE_CONFIG[option.id as keyof typeof CHOICE_CONFIG];
          const Icon = config?.icon ?? Zap;
          const accent = config?.accent ?? '';
          const iconColor = config?.iconColor ?? 'text-muted-foreground';

          return (
            <button
              key={option.id}
              type="button"
              onClick={() => onSubmit(option.id)}
              disabled={isLoading}
              className={cn(
                'flex items-start gap-3 rounded-lg border p-4 text-left transition-all disabled:opacity-50',
                accent,
              )}
            >
              <div
                className={cn(
                  'flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted',
                  iconColor,
                )}
              >
                <Icon className="size-5" />
              </div>
              <div className="space-y-0.5">
                <p className="text-sm font-medium">{option.label}</p>
                <p className="text-xs text-muted-foreground">
                  {option.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
