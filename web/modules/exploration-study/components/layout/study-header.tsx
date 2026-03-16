'use client';

import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

export interface StudyHeaderProps {
  currentStep: number;
  totalSteps: number;
  stepLabel: string;
  className?: string;
}

export function StudyHeader({
  currentStep,
  totalSteps,
  stepLabel,
  className,
}: StudyHeaderProps) {
  const percentage = Math.round((currentStep / totalSteps) * 100);

  return (
    <header
      className={cn(
        'sticky top-0 z-50 flex h-[var(--study-header-height)] flex-col justify-center border-b bg-background px-4',
        className,
      )}
      style={
        {
          '--study-header-height': '64px',
        } as React.CSSProperties
      }
    >
      <div className="mx-auto w-full max-w-2xl">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium text-foreground">{stepLabel}</span>
          <span className="text-muted-foreground">
            Schritt {currentStep} von {totalSteps}
          </span>
        </div>
        <Progress
          value={percentage}
          className="h-2"
          aria-label={`Fortschritt: ${percentage}%`}
        />
      </div>
    </header>
  );
}
