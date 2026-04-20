'use client';

import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@/components/ui/form';
import { cn } from '@/lib/utils';
import { FormItemCard } from '@/modules/exploration-study/components/shared/form-item-card';
import { SemanticDifferential } from '@/modules/exploration-study/components/shared/semantic-differential';
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
      <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
        <div className="space-y-2">
          <h2 className="text-xl font-semibold">Benutzererfahrung</h2>
          <p className="text-sm text-foreground">
            Bitte bewerte das System auf den folgenden Skalen. Wähle für jedes
            Gegensatzpaar den Wert, der deiner Meinung nach am besten zutrifft.
          </p>
        </div>

        <div className="space-y-3">
          {items.map((item, index) => {
            const fieldKey = `item${item.id}` as UeqFieldKey;
            const labelId = `ueq-item-${item.id}-label`;
            return (
              <FormField
                key={item.id}
                control={form.control}
                name={fieldKey}
                render={({ field, fieldState }) => {
                  const answered =
                    field.value !== null && field.value !== undefined;
                  return (
                    <FormItemCard answered={answered}>
                      <FormItem className="space-y-3">
                        <p id={labelId} className="pr-8 text-sm font-medium">
                          Frage {index + 1} von 8
                        </p>
                        <FormControl>
                          <SemanticDifferential
                            id={`ueq-item-${item.id}`}
                            labelledById={labelId}
                            leftAnchor={item.leftAnchor}
                            rightAnchor={item.rightAnchor}
                            value={field.value ?? null}
                            onChange={field.onChange}
                            onBlur={field.onBlur}
                            invalid={!!fieldState.error}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    </FormItemCard>
                  );
                }}
              />
            );
          })}
        </div>

        <SubmitButton isSubmitting={isSubmitting} />
      </form>
    </Form>
  );
}
