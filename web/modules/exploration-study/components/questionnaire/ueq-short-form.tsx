'use client';

import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { LikertFormItem } from '@/modules/exploration-study/components/shared/likert-form-item';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import { useFormItemTiming } from '@/modules/exploration-study/hooks/use-form-item-timing';
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
  // When true, renders an optional free-text field for qualitative studies.
  showQualitativeFeedback?: boolean;
  // Telemetry: called on each Likert change with the field name and the ms
  // since the previous change (straightlining detection).
  onItemAnswered?: (itemId: string, intervalMs: number) => void;
  className?: string;
}

type UeqFieldKey = keyof UeqShortFormValues;

const QUALITATIVE_FEEDBACK_LABEL =
  'Möchtest du noch etwas zu deiner Nutzungserfahrung ergänzen? (optional)';

export function UeqShortForm({
  onSubmit,
  isSubmitting = false,
  showQualitativeFeedback = false,
  onItemAnswered,
  className,
}: UeqShortFormProps) {
  const { items, order } = useMemo(() => getRandomizedUeqItems(), []);

  const form = useForm<UeqShortFormValues>({
    resolver: zodResolver(ueqShortSchema),
    defaultValues: {},
  });

  useFormItemTiming(form, onItemAnswered);

  const handleSubmit = form.handleSubmit((values) => {
    const { qualitativeFeedback, ...ratings } = values;
    onSubmit({
      ...ratings,
      itemOrder: order,
      ...(qualitativeFeedback ? { qualitativeFeedback } : {}),
    });
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

        {showQualitativeFeedback && (
          <FormField
            control={form.control}
            name="qualitativeFeedback"
            render={({ field }) => (
              <FormItem>
                <FormLabel htmlFor="ueq-qualitative-feedback">
                  {QUALITATIVE_FEEDBACK_LABEL}
                </FormLabel>
                <FormControl>
                  <Textarea
                    {...field}
                    id="ueq-qualitative-feedback"
                    value={field.value ?? ''}
                    rows={4}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        <SubmitButton isSubmitting={isSubmitting} />
      </form>
    </Form>
  );
}
