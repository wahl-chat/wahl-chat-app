'use client';

import { Button } from '@/components/ui/button';
import type { ChoicePromptEvent } from '@/modules/guided-exploration/types';

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
  return (
    <div className="space-y-4 rounded-lg border bg-card p-4">
      <p className="text-sm text-muted-foreground">
        Das sieht nach einem komplexen Thema aus. Willst du es strukturiert
        explorieren oder lieber eine Zusammenfassung?
      </p>
      <div className="flex flex-col gap-2 overflow-hidden px-2 sm:flex-row">
        {choice.options.map((option) => (
          <Button
            key={option.id}
            variant={option.id === 'explore' ? 'default' : 'outline'}
            onClick={() => onSubmit(option.id)}
            disabled={isLoading}
            className="h-auto min-w-0 flex-1 py-3"
          >
            <div className="w-full text-wrap text-left">
              <div className="font-medium">{option.label}</div>
              <div className="text-xs opacity-70">{option.description}</div>
            </div>
          </Button>
        ))}
      </div>
    </div>
  );
}
