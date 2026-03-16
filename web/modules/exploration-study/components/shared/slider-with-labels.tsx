'use client';

import { Slider } from '@/components/ui/slider';
import { cn } from '@/lib/utils';

export interface SliderWithLabelsProps {
  id: string;
  label: string;
  description?: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  lowAnchor: string;
  highAnchor: string;
  className?: string;
}

export function SliderWithLabels({
  id,
  label,
  description,
  value,
  onChange,
  min,
  max,
  step = 1,
  lowAnchor,
  highAnchor,
  className,
}: SliderWithLabelsProps) {
  return (
    <div className={cn('space-y-3', className)}>
      <div className="space-y-1">
        <label
          htmlFor={id}
          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
        >
          {label}
        </label>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>

      <div className="space-y-2">
        <Slider
          id={id}
          value={[value]}
          onValueChange={([v]) => onChange(v)}
          min={min}
          max={max}
          step={step}
          aria-label={label}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{lowAnchor}</span>
          <span className="font-medium text-foreground">{value}</span>
          <span>{highAnchor}</span>
        </div>
      </div>
    </div>
  );
}
