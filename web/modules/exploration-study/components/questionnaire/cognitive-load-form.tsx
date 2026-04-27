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
  type CognitiveLoadFormValues,
  cognitiveLoadSchema,
} from '@/modules/exploration-study/schemas/forms';
import {
  COGNITIVE_LOAD_ANCHORS,
  COGNITIVE_LOAD_ITEMS,
  type CognitiveLoadResponse,
} from '@/modules/exploration-study/types';
import { zodResolver } from '@hookform/resolvers/zod';
import type { FieldPath } from 'react-hook-form';
import { useForm } from 'react-hook-form';

export interface CognitiveLoadFormProps {
  onSubmit: (data: CognitiveLoadResponse) => void;
  className?: string;
}

export function CognitiveLoadForm({
  onSubmit,
  className,
}: CognitiveLoadFormProps) {
  const form = useForm<CognitiveLoadFormValues>({
    resolver: zodResolver(cognitiveLoadSchema),
    defaultValues: {},
  });

  const handleSubmit = form.handleSubmit((values) => {
    onSubmit(values);
  });

  return (
    <Form {...form}>
      <form
        onSubmit={handleSubmit}
        aria-labelledby="cognitive-load-heading"
        className={cn('space-y-6', className)}
      >
        <div className="space-y-2">
          <h2 id="cognitive-load-heading" className="text-xl font-semibold">
            Bewertung der Aufgabe
          </h2>
          <p className="text-sm text-foreground">
            Bitte gib für jede Aussage an, wie sehr sie auf die gerade
            bearbeitete Aufgabe zutrifft.
          </p>
        </div>

        <div className="space-y-3">
          {COGNITIVE_LOAD_ITEMS.map((item) => {
            const labelId = `cognitive-load-${item.id}-label`;
            return (
              <FormField
                key={item.id}
                control={form.control}
                name={item.id as FieldPath<CognitiveLoadFormValues>}
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
                          {item.text}
                        </p>
                        <FormControl>
                          <SemanticDifferential
                            id={`cognitive-load-${item.id}`}
                            labelledById={labelId}
                            leftAnchor={COGNITIVE_LOAD_ANCHORS.low}
                            rightAnchor={COGNITIVE_LOAD_ANCHORS.high}
                            min={1}
                            max={7}
                            value={field.value ?? null}
                            onChange={field.onChange}
                            onBlur={field.onBlur}
                            invalid={!!fieldState.error}
                            itemLabel={item.text}
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

        <SubmitButton />
      </form>
    </Form>
  );
}
