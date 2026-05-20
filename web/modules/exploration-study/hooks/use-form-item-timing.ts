'use client';

import { useEffect, useRef } from 'react';
import type { FieldValues, UseFormReturn } from 'react-hook-form';

/**
 * Emit a callback every time a form field's value changes, carrying the
 * elapsed time since the previous change. Used to capture inter-item response
 * intervals on Likert questionnaires — the canonical straightlining signal
 * (a respondent racing through with near-zero, uniform intervals).
 *
 * Content-free: only the field name and the interval in ms are reported.
 */
export function useFormItemTiming<T extends FieldValues>(
  form: UseFormReturn<T>,
  onItemAnswered?: (itemId: string, intervalMs: number) => void,
): void {
  const lastTs = useRef<number>(Date.now());

  useEffect(() => {
    if (!onItemAnswered) return;
    const subscription = form.watch((_values, { name, type }) => {
      if (!name || type !== 'change') return;
      const now = Date.now();
      onItemAnswered(name, now - lastTs.current);
      lastTs.current = now;
    });
    return () => subscription.unsubscribe();
  }, [form, onItemAnswered]);
}
