'use client';

import SkipLink from '@/components/skip-link';
import { cn } from '@/lib/utils';
import type { StudyState } from '@/modules/exploration-study/types';
import { getProgress } from '@/modules/exploration-study/utils';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
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
  const pathname = usePathname();
  const mainRef = useRef<HTMLElement>(null);
  const [announcement, setAnnouncement] = useState('');

  useEffect(() => {
    if (hideHeader) return;
    mainRef.current?.focus({ preventScroll: true });
    setAnnouncement(
      `Schritt ${progress.currentStep} von ${progress.totalSteps}: ${progress.label}`,
    );
  }, [
    pathname,
    hideHeader,
    progress.currentStep,
    progress.totalSteps,
    progress.label,
  ]);

  return (
    <div className="flex min-h-dvh flex-col">
      <SkipLink href="#main-content">Zum Hauptinhalt springen</SkipLink>
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </div>
      {!hideHeader && (
        <StudyHeader
          currentStep={progress.currentStep}
          totalSteps={progress.totalSteps}
          stepLabel={progress.label}
        />
      )}
      {hideHeader ? (
        // Task page: no page-level <main> wrapper. The task screen supplies
        // its own landmarks (progress <header> banner + the task <main>), so
        // wrapping everything here would make <main> swallow the headers.
        <div className={cn('flex flex-1 flex-col', className)}>{children}</div>
      ) : (
        <main
          ref={mainRef}
          id="main-content"
          tabIndex={-1}
          aria-label="Studieninhalt"
          className={cn(
            'flex flex-1 flex-col px-4 pt-8 pb-20 focus:outline-none',
            className,
          )}
        >
          {children}
        </main>
      )}
    </div>
  );
}
