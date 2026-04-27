'use client';

import { Form } from '@/components/ui/form';
import { cn } from '@/lib/utils';
import { LikertFormItem } from '@/modules/exploration-study/components/shared/likert-form-item';
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
              <LikertFormItem
                key={item.id}
                control={form.control}
                name={`mailsShort.${MAILS_KEYS[index]}`}
                id={`mails-item-${item.id}`}
                label={`${item.id}. ${item.text}`}
                leftAnchor="gar nicht ausgeprägt"
                rightAnchor="(nahezu) perfekt"
                min={0}
                max={10}
              />
            ))}
          </div>
        </section>

        <SubmitButton isSubmitting={isSubmitting} />
      </form>
    </Form>
  );
}
