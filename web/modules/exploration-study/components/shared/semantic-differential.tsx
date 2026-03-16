'use client';

import { cn } from '@/lib/utils';
import { useCallback } from 'react';

export interface SemanticDifferentialProps {
  id: string;
  leftAnchor: string;
  rightAnchor: string;
  value: number | null;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  className?: string;
}

export function SemanticDifferential({
  id,
  leftAnchor,
  rightAnchor,
  value,
  onChange,
  min = 1,
  max = 7,
  className,
}: SemanticDifferentialProps) {
  const options = Array.from({ length: max - min + 1 }, (_, i) => min + i);

  // Custom keyboard handling for intuitive arrow key navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, currentValue: number) => {
      let newValue: number | null = null;

      switch (e.key) {
        case 'ArrowRight':
        case 'ArrowUp':
          // Increase value (move right on scale)
          if (currentValue < max) {
            newValue = currentValue + 1;
          }
          break;
        case 'ArrowLeft':
        case 'ArrowDown':
          // Decrease value (move left on scale)
          if (currentValue > min) {
            newValue = currentValue - 1;
          }
          break;
        default:
          return;
      }

      if (newValue !== null) {
        e.preventDefault();
        onChange(newValue);
        // Focus the new radio button
        const nextInput = document.querySelector<HTMLInputElement>(
          `input[name="${id}"][value="${newValue}"]`,
        );
        nextInput?.focus();
      }
    },
    [id, min, max, onChange],
  );

  return (
    <fieldset
      className={cn('space-y-2', className)}
      role="radiogroup"
      aria-label={`${leftAnchor} bis ${rightAnchor}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="min-w-[100px] text-sm font-medium">{leftAnchor}</span>

        <div className="flex flex-1 justify-center gap-1 sm:gap-2">
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
                  'flex size-8 items-center justify-center rounded-full border-2 text-sm transition-colors',
                  'hover:border-primary hover:bg-primary/10',
                  'peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2',
                  value === option
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-muted-foreground/30 bg-background',
                )}
              >
                {option}
              </span>
            </label>
          ))}
        </div>

        <span className="min-w-[100px] text-right text-sm font-medium">
          {rightAnchor}
        </span>
      </div>
    </fieldset>
  );
}
