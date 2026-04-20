'use client';

import { cn } from '@/lib/utils';
import { SliderWithLabels } from '@/modules/exploration-study/components/shared/slider-with-labels';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import {
  NASA_TLX_ITEMS,
  type NasaTlxData,
} from '@/modules/exploration-study/types';
import { useState } from 'react';

export interface NasaTlxFormProps {
  onSubmit: (data: NasaTlxData) => void;
  className?: string;
}

export function NasaTlxForm({ onSubmit, className }: NasaTlxFormProps) {
  const [values, setValues] = useState<NasaTlxData>({
    mentalDemand: 11,
    physicalDemand: 11,
    temporalDemand: 11,
    performance: 11,
    effort: 11,
    frustration: 11,
  });

  const handleChange = (key: keyof NasaTlxData, value: number) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(values);
  };

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Arbeitsbelastung</h2>
        <p className="text-sm text-foreground">
          Bitte bewerte die verschiedenen Aspekte der Arbeitsbelastung während
          der Aufgabe.
        </p>
      </div>

      <div className="space-y-8">
        {NASA_TLX_ITEMS.map((item) => (
          <SliderWithLabels
            key={item.key}
            id={`nasa-tlx-${item.key}`}
            label={item.label}
            description={item.description}
            value={values[item.key]}
            onChange={(value) => handleChange(item.key, value)}
            min={1}
            max={21}
            lowAnchor={item.lowAnchor}
            highAnchor={item.highAnchor}
          />
        ))}
      </div>

      <SubmitButton />
    </form>
  );
}
