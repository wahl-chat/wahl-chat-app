'use client';

import { cn } from '@/lib/utils';
import { forwardRef, useCallback } from 'react';

export interface RatingScaleProps {
  id: string;
  min: number;
  max: number;
  value: number | null;
  onChange: (value: number) => void;
  onBlur?: () => void;
  lowAnchor?: string;
  highAnchor?: string;
  /**
   * Id of a visible element (e.g. the statement above the scale) that
   * describes what is being rated. Wired through to the radiogroup's
   * accessible name.
   */
  labelledById?: string;
  /**
   * 'md' (default): size-8 circles, gap-2 — good for scales up to ~7 options.
   * 'sm': size-7 circles, gap-1 — fits 11 circles (MAILS 0-10) on mobile.
   */
  size?: 'sm' | 'md';
  className?: string;
  /**
   * When true, the radiogroup is marked invalid for screen readers.
   */
  invalid?: boolean;
  /**
   * Id of the error message element, wired into aria-describedby when set.
   */
  describedById?: string;
  /**
   * When true, the radiogroup is marked as required for screen readers.
   */
  required?: boolean;
}

export const RatingScale = forwardRef<HTMLDivElement, RatingScaleProps>(
  function RatingScale(
    {
      id,
      min,
      max,
      value,
      onChange,
      onBlur,
      lowAnchor,
      highAnchor,
      labelledById,
      size = 'md',
      className,
      invalid,
      describedById,
      required,
    },
    ref,
  ) {
    const options = Array.from({ length: max - min + 1 }, (_, i) => min + i);

    const handleKeyDown = useCallback(
      (e: React.KeyboardEvent, currentValue: number) => {
        let next: number | null = null;
        switch (e.key) {
          case 'ArrowRight':
          case 'ArrowUp':
            if (currentValue < max) next = currentValue + 1;
            break;
          case 'ArrowLeft':
          case 'ArrowDown':
            if (currentValue > min) next = currentValue - 1;
            break;
          default:
            return;
        }
        if (next !== null) {
          e.preventDefault();
          onChange(next);
          const nextInput = document.querySelector<HTMLInputElement>(
            `input[name="${id}"][value="${next}"]`,
          );
          nextInput?.focus();
        }
      },
      [id, min, max, onChange],
    );

    const fallbackAnchorsId = `${id}-anchors`;
    const labelledBy = labelledById ?? fallbackAnchorsId;

    return (
      <div
        ref={ref}
        tabIndex={-1}
        role="radiogroup"
        aria-labelledby={labelledBy}
        aria-invalid={invalid || undefined}
        aria-describedby={describedById}
        aria-required={required || undefined}
        className={cn('space-y-2 outline-none', className)}
        onBlur={onBlur}
      >
        {!labelledById && (
          <span id={fallbackAnchorsId} className="sr-only">
            {lowAnchor && highAnchor
              ? `${lowAnchor} bis ${highAnchor}`
              : `Skala von ${min} bis ${max}`}
          </span>
        )}
        <div
          className={cn(
            'flex flex-wrap items-center justify-center',
            size === 'sm' ? 'gap-1 sm:gap-1.5' : 'gap-1.5 sm:gap-2',
          )}
        >
          {options.map((option) => (
            <label key={option} className="relative cursor-pointer">
              <input
                type="radio"
                name={id}
                value={option}
                checked={value === option}
                onChange={() => onChange(option)}
                onKeyDown={(e) => handleKeyDown(e, option)}
                className="peer sr-only"
                aria-label={`${option} von ${max}`}
              />
              <span
                className={cn(
                  'flex items-center justify-center rounded-full border-2 text-sm transition-colors',
                  size === 'sm' ? 'size-7' : 'size-8',
                  'peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2',
                  value === option
                    ? 'border-primary bg-primary text-primary-foreground hover:border-muted-foreground/30 hover:bg-muted hover:text-foreground'
                    : 'border-muted-foreground/30 bg-background hover:border-primary hover:bg-primary/10',
                )}
              >
                {option}
              </span>
            </label>
          ))}
        </div>
        {(lowAnchor || highAnchor) && (
          <div
            aria-hidden="true"
            className="flex justify-between text-xs text-muted-foreground"
          >
            <span>{lowAnchor}</span>
            <span>{highAnchor}</span>
          </div>
        )}
      </div>
    );
  },
);
