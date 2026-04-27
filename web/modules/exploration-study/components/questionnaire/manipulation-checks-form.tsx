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
  type ManipulationChecksFormValues,
  manipulationChecksSchema,
} from '@/modules/exploration-study/schemas/forms';
import {
  MANIPULATION_CHECK_ITEMS,
  type ManipulationChecksData,
} from '@/modules/exploration-study/types';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

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
  const form = useForm<ManipulationChecksFormValues>({
    resolver: zodResolver(manipulationChecksSchema),
    defaultValues: {},
  });

  const handleSubmit = form.handleSubmit((values) => {
    onSubmit(values);
  });

  return (
    <Form {...form}>
      <form
        onSubmit={handleSubmit}
        aria-labelledby="manipulation-checks-heading"
        className={cn('space-y-6', className)}
      >
        <div className="space-y-2">
          <h2
            id="manipulation-checks-heading"
            className="text-xl font-semibold"
          >
            Allgemeine Einschätzung
          </h2>
          <p className="text-sm text-foreground">
            Bitte bewerte die folgenden Aussagen.
          </p>
        </div>

        <div className="space-y-3">
          {MANIPULATION_CHECK_ITEMS.map((item) => {
            const labelId = `manipulation-check-${item.key}-label`;
            return (
              <FormField
                key={item.key}
                control={form.control}
                name={item.key}
                render={({ field, fieldState }) => {
                  const answered =
                    field.value !== null && field.value !== undefined;
                  return (
                    <FormItemCard answered={answered}>
                      <FormItem className="space-y-4">
                        <p
                          id={labelId}
                          className="pr-8 text-base font-semibold leading-snug text-foreground"
                        >
                          {item.label}
                        </p>
                        <FormControl>
                          <SemanticDifferential
                            id={`manipulation-check-${item.key}`}
                            labelledById={labelId}
                            leftAnchor="Stimme nicht zu"
                            rightAnchor="Stimme zu"
                            min={1}
                            max={5}
                            value={field.value ?? null}
                            onChange={field.onChange}
                            onBlur={field.onBlur}
                            invalid={!!fieldState.error}
                            itemLabel={item.label}
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
