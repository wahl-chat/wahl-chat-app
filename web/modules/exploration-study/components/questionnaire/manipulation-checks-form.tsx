'use client';

import { Form } from '@/components/ui/form';
import { cn } from '@/lib/utils';
import { LikertFormItem } from '@/modules/exploration-study/components/shared/likert-form-item';
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
          {MANIPULATION_CHECK_ITEMS.map((item) => (
            <LikertFormItem
              key={item.key}
              control={form.control}
              name={item.key}
              id={`manipulation-check-${item.key}`}
              label={item.label}
              leftAnchor="Stimme nicht zu"
              rightAnchor="Stimme zu"
              min={1}
              max={5}
            />
          ))}
        </div>

        <SubmitButton isSubmitting={isSubmitting} />
      </form>
    </Form>
  );
}
