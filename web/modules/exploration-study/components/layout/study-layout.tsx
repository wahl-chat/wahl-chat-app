'use client';

import { cn } from '@/lib/utils';
import type { StudyState } from '@/modules/exploration-study/types';
import { getProgress } from '@/modules/exploration-study/utils';
import { StudyHeader } from './study-header';

export interface StudyLayoutProps {
  state: StudyState;
  children: React.ReactNode;
  className?: string;
  hideHeader?: boolean;
}

export function StudyLayout({
  state,
  children,
  className,
  hideHeader = false,
}: StudyLayoutProps) {
  const progress = getProgress(state);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {!hideHeader && (
        <StudyHeader
          currentStep={progress.currentStep}
          totalSteps={progress.totalSteps}
          stepLabel={progress.label}
        />
      )}
      <main
        aria-label="Studieninhalt"
        className={cn(
          'flex flex-1 flex-col',
          !hideHeader && 'px-4 pt-8 pb-20',
          className,
        )}
      >
        {children}
      </main>
    </div>
  );
}
