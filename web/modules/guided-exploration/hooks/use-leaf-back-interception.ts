'use client';

import { useEffect, useRef } from 'react';

interface UseLeafBackInterceptionOptions {
  /** Whether the leaf sheet is currently open. */
  isOpen: boolean;
  /** Called when the user presses the browser back button. */
  onBack: () => void;
}

/**
 * Intercepts browser back navigation while a sheet/modal is open: the
 * first back press closes the sheet via `onBack()` instead of leaving
 * the page. On mobile this matches the platform expectation.
 *
 * Implementation: when the sheet opens, pushes a sentinel history entry
 * and listens for `popstate`. An explicit close (X button / programmatic
 * close that flips `isOpen` to `false`) pops the sentinel itself so we
 * never leave a stray entry behind. A ref guards against React Strict
 * Mode's double-mount accidentally pushing twice or popping immediately.
 */
export function useLeafBackInterception({
  isOpen,
  onBack,
}: UseLeafBackInterceptionOptions): void {
  const pushedRef = useRef(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handlePopState = () => {
      if (!pushedRef.current) return;
      pushedRef.current = false;
      onBack();
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [onBack]);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    if (isOpen && !pushedRef.current) {
      window.history.pushState({ __leafSheet: true }, '');
      pushedRef.current = true;
      return;
    }

    if (!isOpen && pushedRef.current) {
      pushedRef.current = false;
      const current = window.history.state as { __leafSheet?: boolean } | null;
      if (current?.__leafSheet) {
        window.history.back();
      }
    }
  }, [isOpen]);
}
