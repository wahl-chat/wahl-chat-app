'use client';

import { cn } from '@/lib/utils';
import { SemanticDifferential } from '@/modules/exploration-study/components/shared/semantic-differential';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import {
  MANIPULATION_CHECK_ITEMS,
  type ManipulationChecksData,
} from '@/modules/exploration-study/types';
import { useState } from 'react';

export interface ManipulationChecksFormProps {
  onSubmit: (data: ManipulationChecksData) => void;
  isSubmitting?: boolean;
  className?: string;
}

export function ManipulationChecksForm({
  onSubmit,
  isSubmitting = false,
  className,
}: ManipulationChecksFormProps) {
  const [responses, setResponses] = useState<
    Partial<Record<keyof ManipulationChecksData, number>>
  >({});

  const isComplete = MANIPULATION_CHECK_ITEMS.every(
    (item) => responses[item.key] !== undefined,
  );

  const handleChange = (key: keyof ManipulationChecksData, value: number) => {
    setResponses((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isComplete) {
      onSubmit(responses as ManipulationChecksData);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Allgemeine Einschätzung</h2>
        <p className="text-sm text-muted-foreground">
          Bitte bewerte die folgenden Aussagen.
        </p>
      </div>

      <div className="space-y-6">
        {MANIPULATION_CHECK_ITEMS.map((item) => (
          <div key={item.key} className="space-y-2">
            <p className="text-sm font-medium">{item.label}</p>
            <SemanticDifferential
              id={`manipulation-check-${item.key}`}
              leftAnchor="Stimme nicht zu"
              rightAnchor="Stimme zu"
              value={responses[item.key] ?? null}
              onChange={(value) => handleChange(item.key, value)}
              min={1}
              max={5}
            />
          </div>
        ))}
      </div>

      <SubmitButton isSubmitting={isSubmitting} disabled={!isComplete} />
    </form>
  );
}
