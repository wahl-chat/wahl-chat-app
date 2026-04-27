'use client';

import { cn } from '@/lib/utils';
import { forwardRef } from 'react';
import { RatingScale } from './rating-scale';

export interface SemanticDifferentialProps {
  id: string;
  leftAnchor: string;
  rightAnchor: string;
  value: number | null;
  onChange: (value: number) => void;
  onBlur?: () => void;
  min?: number;
  max?: number;
  className?: string;
  /**
   * Id of a visible element that describes what is being rated (e.g. the
   * question text above the scale). Wired into the radiogroup's accessible
   * name alongside the anchor pair.
   */
  labelledById?: string;
  invalid?: boolean;
  describedById?: string;
  /**
   * Short description that prefixes each radio's accessible name so the
   * Form Controls rotor is scannable. Defaults to "{leftAnchor} bis
   * {rightAnchor}" when omitted.
   */
  itemLabel?: string;
}

export const SemanticDifferential = forwardRef<
  HTMLDivElement,
  SemanticDifferentialProps
>(function SemanticDifferential(
  {
    id,
    leftAnchor,
    rightAnchor,
    value,
    onChange,
    onBlur,
    min = 1,
    max = 7,
    className,
    labelledById,
    invalid,
    describedById,
    itemLabel,
  },
  ref,
) {
  const anchorPairId = `${id}-anchor-pair`;
  const effectiveItemLabel = itemLabel ?? `${leftAnchor} bis ${rightAnchor}`;

  return (
    <div className={cn('space-y-1', className)}>
      <span id={anchorPairId} className="sr-only">
        {`${leftAnchor} bis ${rightAnchor}`}
      </span>
      <div className="flex items-center justify-between gap-2">
        <span
          aria-hidden="true"
          className="min-w-[90px] text-xs font-normal text-muted-foreground"
        >
          {leftAnchor}
        </span>

        <div className="flex flex-1 justify-center">
          <RatingScale
            ref={ref}
            id={id}
            min={min}
            max={max}
            value={value}
            onChange={onChange}
            onBlur={onBlur}
            labelledById={
              labelledById ? `${labelledById} ${anchorPairId}` : anchorPairId
            }
            invalid={invalid}
            describedById={describedById}
            itemLabel={effectiveItemLabel}
          />
        </div>

        <span
          aria-hidden="true"
          className="min-w-[90px] text-right text-xs font-normal text-muted-foreground"
        >
          {rightAnchor}
        </span>
      </div>
    </div>
  );
});
