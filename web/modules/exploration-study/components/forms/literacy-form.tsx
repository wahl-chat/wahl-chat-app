'use client';

import { Checkbox } from '@/components/ui/checkbox';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormMessage,
} from '@/components/ui/form';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { FormItemCard } from '@/modules/exploration-study/components/shared/form-item-card';
import { RatingScale } from '@/modules/exploration-study/components/shared/rating-scale';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import type { LiteracyFormValues } from '@/modules/exploration-study/schemas/forms';
import { literacySchema } from '@/modules/exploration-study/schemas/forms';
import type {
  LiteracyData,
  MailsShortData,
  NewsSource,
} from '@/modules/exploration-study/types';
import {
  MAILS_SHORT_INTRO,
  MAILS_SHORT_ITEMS,
} from '@/modules/exploration-study/types';
import { zodResolver } from '@hookform/resolvers/zod';
import { CheckCircle2 } from 'lucide-react';
import type { Control } from 'react-hook-form';
import { useForm } from 'react-hook-form';

export interface LiteracyFormProps {
  onSubmit: (data: LiteracyData) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

const NEWS_SOURCE_OPTIONS: { value: NewsSource; label: string }[] = [
  { value: 'online', label: 'Online-Nachrichtenseiten' },
  { value: 'tv', label: 'Fernsehen' },
  { value: 'newspaper', label: 'Zeitungen / Zeitschriften' },
  { value: 'social_media', label: 'Soziale Medien' },
  { value: 'radio', label: 'Radio' },
];

const MAILS_KEYS: (keyof MailsShortData)[] = [
  'item1',
  'item2',
  'item3',
  'item4',
  'item5',
  'item6',
  'item7',
  'item8',
  'item9',
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
      newsConsumption: [],
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
            Umgang mit künstlicher Intelligenz und zu deinem Nachrichtenkonsum.
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

        <FormField
          control={form.control}
          name="newsConsumption"
          render={({ field, fieldState }) => {
            const value = field.value ?? [];
            const answered = value.length > 0;
            const toggle = (source: NewsSource) => {
              if (value.includes(source)) {
                field.onChange(value.filter((s) => s !== source));
              } else {
                field.onChange([...value, source]);
              }
            };
            const errorId = 'news-consumption-error';
            const descriptionId = 'news-consumption-description';
            return (
              <FormItem>
                <fieldset
                  className="space-y-3"
                  aria-invalid={!!fieldState.error}
                  aria-describedby={
                    fieldState.error
                      ? `${descriptionId} ${errorId}`
                      : descriptionId
                  }
                >
                  <legend className="inline-flex items-center gap-1.5 text-sm font-medium">
                    Über welche Quellen informierst du dich über politische
                    Themen?
                    {answered && (
                      <>
                        <CheckCircle2
                          className="size-4 text-primary"
                          aria-hidden="true"
                        />
                        <span className="sr-only">(ausgefüllt)</span>
                      </>
                    )}
                  </legend>
                  <p id={descriptionId} className="text-sm text-foreground">
                    Mehrfachauswahl möglich
                  </p>
                  <div className="space-y-2">
                    {NEWS_SOURCE_OPTIONS.map((option) => {
                      const checked = value.includes(option.value);
                      const checkboxId = `news-source-${option.value}`;
                      return (
                        <div
                          key={option.value}
                          className={cn(
                            'flex items-center gap-3 rounded-lg border p-3 transition-colors',
                            checked
                              ? 'border-primary/40 bg-primary/5'
                              : 'border-border bg-card',
                          )}
                        >
                          <Checkbox
                            id={checkboxId}
                            checked={checked}
                            onCheckedChange={() => toggle(option.value)}
                          />
                          <Label
                            htmlFor={checkboxId}
                            className="flex-1 cursor-pointer text-sm font-normal"
                          >
                            {option.label}
                          </Label>
                        </div>
                      );
                    })}
                  </div>
                  <FormMessage id={errorId} />
                </fieldset>
              </FormItem>
            );
          }}
        />

        <SubmitButton isSubmitting={isSubmitting} />
      </form>
    </Form>
  );
}
