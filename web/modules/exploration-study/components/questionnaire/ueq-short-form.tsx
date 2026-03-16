'use client';

import { cn } from '@/lib/utils';
import { SemanticDifferential } from '@/modules/exploration-study/components/shared/semantic-differential';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import type { UeqData } from '@/modules/exploration-study/types';
import { getRandomizedUeqItems } from '@/modules/exploration-study/utils';
import { useMemo, useState } from 'react';

export interface UeqShortFormProps {
  onSubmit: (data: UeqData) => void;
  isSubmitting?: boolean;
  className?: string;
}

export function UeqShortForm({
  onSubmit,
  isSubmitting = false,
  className,
}: UeqShortFormProps) {
  // Randomize item order on mount
  const { items, order } = useMemo(() => getRandomizedUeqItems(), []);

  const [values, setValues] = useState<Record<number, number | null>>(() =>
    Object.fromEntries(items.map((item) => [item.id, null])),
  );

  const handleChange = (itemId: number, value: number) => {
    setValues((prev) => ({ ...prev, [itemId]: value }));
  };

  const allAnswered = Object.values(values).every((v) => v !== null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!allAnswered) return;

    // All values are guaranteed non-null by allAnswered check
    const v = values as Record<number, number>;
    onSubmit({
      item1: v[1],
      item2: v[2],
      item3: v[3],
      item4: v[4],
      item5: v[5],
      item6: v[6],
      item7: v[7],
      item8: v[8],
      itemOrder: order,
    });
  };

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Benutzererfahrung</h2>
        <p className="text-sm text-muted-foreground">
          Bitte bewerte das System auf den folgenden Skalen. Wähle für jedes
          Gegensatzpaar den Wert, der deiner Meinung nach am besten zutrifft.
        </p>
      </div>

      <div className="space-y-6">
        {items.map((item, index) => (
          <div key={item.id} className="space-y-2">
            <p className="text-sm font-medium">Frage {index + 1} von 8</p>
            <SemanticDifferential
              id={`ueq-item-${item.id}`}
              leftAnchor={item.leftAnchor}
              rightAnchor={item.rightAnchor}
              value={values[item.id]}
              onChange={(value) => handleChange(item.id, value)}
            />
          </div>
        ))}
      </div>

      <SubmitButton isSubmitting={isSubmitting} disabled={!allAnswered} />
    </form>
  );
}
