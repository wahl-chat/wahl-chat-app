'use client';

import {
  Form,
  FormControl,
  FormField,
  FormMessage,
} from '@/components/ui/form';
import { cn } from '@/lib/utils';
import { FormItemCard } from '@/modules/exploration-study/components/shared/form-item-card';
import { RatingScale } from '@/modules/exploration-study/components/shared/rating-scale';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import type { LiteracyFormValues } from '@/modules/exploration-study/schemas/forms';
import { literacySchema } from '@/modules/exploration-study/schemas/forms';
import type {
  LiteracyData,
  MailsShortData,
} from '@/modules/exploration-study/types';
import {
  MAILS_SHORT_INTRO,
  MAILS_SHORT_ITEMS,
} from '@/modules/exploration-study/types';
import { zodResolver } from '@hookform/resolvers/zod';
import type { Control } from 'react-hook-form';
import { useForm } from 'react-hook-form';

export interface LiteracyFormProps {
  onSubmit: (data: LiteracyData) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

const MAILS_KEYS: (keyof MailsShortData)[] = [
  'item1',
  'item5',
  'item7',
  'item10',
];

interface MailsRowProps {
  control: Control<LiteracyFormValues>;
  fieldKey: keyof MailsShortData;
  itemId: number;
  itemText: string;
}

function MailsRow({ control, fieldKey, itemId, itemText }: MailsRowProps) {
  const labelId = `mails-item-${itemId}-label`;
  return (
    <FormField
      control={control}
      name={`mailsShort.${fieldKey}`}
      render={({ field, fieldState }) => {
        const answered = field.value !== null && field.value !== undefined;
        return (
          <FormItemCard answered={answered}>
            <p
              id={labelId}
              className="pr-8 text-sm font-medium leading-relaxed"
            >
              <span className="mr-2 text-foreground">{itemId}.</span>
              {itemText}
            </p>
            <FormControl>
              <RatingScale
                id={`mails-item-${itemId}`}
                size="sm"
                min={0}
                max={10}
                value={field.value ?? null}
                onChange={field.onChange}
                onBlur={field.onBlur}
                lowAnchor="gar nicht ausgeprägt"
                highAnchor="(nahezu) perfekt"
                labelledById={labelId}
                invalid={!!fieldState.error}
                required
                className="mt-3"
              />
            </FormControl>
            <FormMessage className="mt-2" />
          </FormItemCard>
        );
      }}
    />
  );
}

export function LiteracyForm({
  onSubmit,
  isSubmitting = false,
  className,
}: LiteracyFormProps) {
  const form = useForm<LiteracyFormValues>({
    resolver: zodResolver(literacySchema),
    defaultValues: {
      mailsShort: {},
    },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    await onSubmit(values);
  });

  return (
    <Form {...form}>
      <form
        onSubmit={handleSubmit}
        aria-labelledby="literacy-heading"
        className={cn('space-y-8', className)}
      >
        <div className="space-y-2">
          <h1 id="literacy-heading" className="text-2xl font-bold">
            Digitale Kompetenz
          </h1>
          <p className="text-sm text-foreground">
            Bitte beantworte die folgenden Fragen zu deinen Fähigkeiten im
            Umgang mit künstlicher Intelligenz.
          </p>
        </div>

        <section className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-base font-semibold">
              Fähigkeiten im Umgang mit KI
            </h2>
            <p className="whitespace-pre-line text-sm text-foreground">
              {MAILS_SHORT_INTRO}
            </p>
          </div>
          <div className="space-y-3">
            {MAILS_SHORT_ITEMS.map((item, index) => (
              <MailsRow
                key={item.id}
                control={form.control}
                fieldKey={MAILS_KEYS[index]}
                itemId={item.id}
                itemText={item.text}
              />
            ))}
          </div>
        </section>

        <SubmitButton isSubmitting={isSubmitting} />
      </form>
    </Form>
  );
}
