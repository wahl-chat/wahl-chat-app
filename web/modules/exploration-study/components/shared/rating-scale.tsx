'use client';

import { cn } from '@/lib/utils';
import { type ReactNode, forwardRef } from 'react';

export interface RatingScaleProps {
  id: string;
  /**
   * Question / item text rendered inside the fieldset's <legend>. AT picks
   * this up natively as the group's accessible name — no aria-labelledby
   * plumbing needed.
   */
  legend: ReactNode;
  min: number;
  max: number;
  value: number | null;
  onChange: (value: number) => void;
  onBlur?: () => void;
  lowAnchor?: string;
  highAnchor?: string;
  /**
   * 'md' (default): size-8 circles, gap-2 — good for scales up to ~7 options.
   * 'sm': size-7 circles, gap-1 — fits 11-point scales (0-10) on mobile.
   */
  size?: 'sm' | 'md';
  className?: string;
  /**
   * Marks each radio as required so native HTML form validation kicks in.
   */
  required?: boolean;
}

/**
 * Pure-HTML Likert scale. Uses a real `<fieldset>` + `<legend>` for
 * grouping (so screen readers announce the question on entry) and native
 * `<input type="radio">` siblings sharing a `name` (so the browser handles
 * arrow-key navigation, roving focus, and the "checked is the tab stop"
 * rule for free).
 *
 * Endpoint radios include the anchor word in their accessible name —
 * VoiceOver users hear "1 – Stimme nicht zu" / "5 – Stimme zu" instead of
 * a bare "1 von 5" with no semantic pole.
 */
export const RatingScale = forwardRef<HTMLFieldSetElement, RatingScaleProps>(
  function RatingScale(
    {
      id,
      legend,
      min,
      max,
      value,
      onChange,
      onBlur,
      lowAnchor,
      highAnchor,
      size = 'md',
      className,
      required,
    },
    ref,
  ) {
    const options = Array.from({ length: max - min + 1 }, (_, i) => min + i);

    return (
      <fieldset
        ref={ref}
        // Reset default UA fieldset chrome (border + min-inline-size). Tailwind's
        // preflight already zeroes margin/padding.
        className={cn('m-0 min-w-0 border-0 p-0', className)}
        onBlur={onBlur}
      >
        <legend className="mb-4 block w-full pr-8 text-sm font-bold leading-snug text-foreground">
          {legend}
        </legend>
        <div className="space-y-2">
          <div
            className={cn(
              'flex flex-wrap items-center justify-center',
              size === 'sm' ? 'gap-1 sm:gap-1.5' : 'gap-1.5 sm:gap-2',
            )}
          >
            {options.map((option) => {
              const isMin = option === min;
              const isMax = option === max;
              // Endpoint radios bake the anchor word into the accessible
              // name so SR users hear which side means what at every focus.
              // Midpoints stay numeric — naming all 5/7 points "1 von 5",
              // "2 von 5"… is the standard Likert pattern.
              const ariaLabel =
                isMin && lowAnchor
                  ? `${option} – ${lowAnchor}`
                  : isMax && highAnchor
                    ? `${option} – ${highAnchor}`
                    : `${option}`;
              return (
                <label
                  key={option}
                  className={cn(
                    'relative cursor-pointer',
                    size === 'sm' ? 'size-7' : 'size-8',
                  )}
                >
                  <input
                    type="radio"
                    name={id}
                    value={option}
                    checked={value === option}
                    onChange={() => onChange(option)}
                    required={required}
                    aria-label={ariaLabel}
                    // Fills the visible circle's footprint instead of the
                    // 1×1 sr-only trick — iOS VoiceOver touch-explore can
                    // actually land on it. Keep `peer` so the visible span
                    // can react to focus/checked state.
                    className="peer absolute inset-0 cursor-pointer opacity-0"
                  />
                  <span
                    aria-hidden="true"
                    className={cn(
                      'flex size-full items-center justify-center rounded-full border-2 text-sm transition-colors',
                      'peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2',
                      value === option
                        ? 'border-primary bg-primary text-primary-foreground hover:border-muted-foreground/30 hover:bg-muted hover:text-foreground'
                        : 'border-muted-foreground/30 bg-background hover:border-primary hover:bg-primary/10',
                    )}
                  >
                    {option}
                  </span>
                </label>
              );
            })}
          </div>
          {(lowAnchor || highAnchor) && (
            // Visible anchor row for sighted users. Hidden from AT — the
            // anchors are already conveyed via the endpoint radios'
            // aria-labels, so reading them again here would be redundant.
            <div
              aria-hidden="true"
              className="flex justify-between text-xs text-foreground"
            >
              <span>{lowAnchor}</span>
              <span>{highAnchor}</span>
            </div>
          )}
        </div>
      </fieldset>
    );
  },
);
