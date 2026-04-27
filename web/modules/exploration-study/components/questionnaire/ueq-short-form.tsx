'use client';

import { Form } from '@/components/ui/form';
import { cn } from '@/lib/utils';
import { LikertFormItem } from '@/modules/exploration-study/components/shared/likert-form-item';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import {
  type UeqShortFormValues,
  ueqShortSchema,
} from '@/modules/exploration-study/schemas/forms';
import type { UeqData } from '@/modules/exploration-study/types';
import { getRandomizedUeqItems } from '@/modules/exploration-study/utils';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMemo } from 'react';
import { useForm } from 'react-hook-form';

export interface UeqShortFormProps {
  onSubmit: (data: UeqData) => void;
  isSubmitting?: boolean;
  className?: string;
}

type UeqFieldKey = keyof UeqShortFormValues;

export function UeqShortForm({
  onSubmit,
  isSubmitting = false,
  className,
}: UeqShortFormProps) {
  const { items, order } = useMemo(() => getRandomizedUeqItems(), []);

  const form = useForm<UeqShortFormValues>({
    resolver: zodResolver(ueqShortSchema),
    defaultValues: {},
  });

  const handleSubmit = form.handleSubmit((values) => {
    onSubmit({ ...values, itemOrder: order });
  });

  return (
    <Form {...form}>
      <form
        onSubmit={handleSubmit}
        aria-labelledby="ueq-heading"
        className={cn('space-y-6', className)}
      >
        <div className="space-y-2">
          <h2 id="ueq-heading" className="text-xl font-semibold">
            Benutzererfahrung
          </h2>
          <p className="text-sm text-foreground">
            Bitte bewerte das System auf den folgenden Skalen. Wähle für jedes
            Gegensatzpaar den Wert, der deiner Meinung nach am besten zutrifft.
          </p>
        </div>

        <div className="space-y-3">
          {items.map((item) => {
            const fieldKey = `item${item.id}` as UeqFieldKey;
            return (
              <LikertFormItem
                key={item.id}
                control={form.control}
                name={fieldKey}
                id={`ueq-item-${item.id}`}
                label={`${item.leftAnchor} – ${item.rightAnchor}`}
                leftAnchor={item.leftAnchor}
                rightAnchor={item.rightAnchor}
                min={1}
                max={7}
              />
            );
          })}
        </div>

        <SubmitButton isSubmitting={isSubmitting} />
      </form>
    </Form>
  );
}
