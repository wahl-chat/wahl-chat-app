'use client';

import { ThemeModeToggle } from '@/components/chat/theme-mode-toggle';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { useTheme } from 'next-themes';
import { useEffect } from 'react';

const STUDY_THEME_INIT_KEY = 'study-theme-initialized';

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
  const { setTheme } = useTheme();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (sessionStorage.getItem(STUDY_THEME_INIT_KEY)) return;
    sessionStorage.setItem(STUDY_THEME_INIT_KEY, '1');
    setTheme('system');
  }, [setTheme]);

  return (
    <header
      className={cn(
        'sticky top-0 z-50 flex h-[var(--study-header-height)] items-center border-b bg-background px-4',
        className,
      )}
      style={
        {
          '--study-header-height': '64px',
        } as React.CSSProperties
      }
    >
      <div className="mx-auto flex w-full max-w-2xl min-w-0 flex-col">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium text-foreground">{stepLabel}</span>
          <span className="text-foreground">
            Schritt {currentStep} von {totalSteps}
          </span>
        </div>
        <Progress value={percentage} className="h-2" aria-label="Fortschritt" />
      </div>
      <div className="ml-4 shrink-0">
        <ThemeModeToggle align="end" showLabel />
      </div>
    </header>
  );
}
