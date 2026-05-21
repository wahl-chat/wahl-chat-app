'use client';

import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { LikertFormItem } from '@/modules/exploration-study/components/shared/likert-form-item';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import {
  type DemographicsFormValues,
  demographicsSchema,
} from '@/modules/exploration-study/schemas/forms';
import type {
  AgeRange,
  AiChatUsageFrequency,
  DemographicsData,
  Education,
  Gender,
} from '@/modules/exploration-study/types';
import { zodResolver } from '@hookform/resolvers/zod';
import { CheckCircle2 } from 'lucide-react';
import { useForm } from 'react-hook-form';

export interface DemographicsFormProps {
  onSubmit: (data: DemographicsData) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

const AGE_RANGE_OPTIONS: { value: AgeRange; label: string }[] = [
  { value: '18-24', label: '18-24 Jahre' },
  { value: '25-34', label: '25-34 Jahre' },
  { value: '35-44', label: '35-44 Jahre' },
  { value: '45-54', label: '45-54 Jahre' },
  { value: '55-64', label: '55-64 Jahre' },
  { value: '65+', label: '65 Jahre oder älter' },
];

const GENDER_OPTIONS: { value: Gender; label: string }[] = [
  { value: 'male', label: 'Männlich' },
  { value: 'female', label: 'Weiblich' },
  { value: 'diverse', label: 'Divers' },
  { value: 'prefer_not_to_say', label: 'Keine Angabe' },
];

const EDUCATION_OPTIONS: { value: Education; label: string }[] = [
  { value: 'no_degree', label: 'Kein Schulabschluss' },
  { value: 'hauptschule', label: 'Hauptschulabschluss' },
  { value: 'realschule', label: 'Realschulabschluss / Mittlere Reife' },
  { value: 'abitur', label: 'Abitur / Fachabitur' },
  { value: 'bachelor', label: 'Bachelor' },
  { value: 'master', label: 'Master / Diplom / Magister' },
  { value: 'doctorate', label: 'Promotion' },
  { value: 'other', label: 'Sonstiges' },
];

const AI_CHAT_USAGE_OPTIONS: { value: AiChatUsageFrequency; label: string }[] =
  [
    { value: 'never', label: 'Nie' },
    {
      value: 'less_than_monthly',
      label: 'Seltener als einmal pro Monat',
    },
    { value: 'several_times_per_month', label: 'Mehrmals pro Monat' },
    { value: 'several_times_per_week', label: 'Mehrmals pro Woche' },
    { value: 'almost_daily', label: '(Fast) täglich' },
  ];

function LabelWithCheck({
  label,
  answered,
}: {
  label: string;
  answered: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {label}
      {answered && (
        <>
          <CheckCircle2 className="size-4 text-primary" aria-hidden="true" />
          <span className="sr-only">(ausgefüllt)</span>
        </>
      )}
    </span>
  );
}

export function DemographicsForm({
  onSubmit,
  isSubmitting = false,
  className,
}: DemographicsFormProps) {
  const form = useForm<DemographicsFormValues>({
    resolver: zodResolver(demographicsSchema),
    defaultValues: {
      ageRange: undefined,
      gender: undefined,
      education: undefined,
    },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    await onSubmit(values);
  });

  return (
    <Form {...form}>
      <form
        onSubmit={handleSubmit}
        aria-labelledby="demographics-heading"
        className={cn('space-y-6', className)}
      >
        <div className="space-y-2">
          <h1 id="demographics-heading" className="text-2xl font-bold">
            Demografische Angaben
          </h1>
          <p className="text-sm text-foreground">
            Bitte beantworte die folgenden Fragen zu deiner Person.
          </p>
        </div>

        <div className="space-y-4">
          <FormField
            control={form.control}
            name="ageRange"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  <LabelWithCheck
                    label="Altersgruppe"
                    answered={!!field.value}
                  />
                </FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger aria-required="true">
                      <SelectValue placeholder="Bitte auswählen" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {AGE_RANGE_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="gender"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  <LabelWithCheck label="Geschlecht" answered={!!field.value} />
                </FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger aria-required="true">
                      <SelectValue placeholder="Bitte auswählen" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {GENDER_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="education"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  <LabelWithCheck
                    label="Höchster Bildungsabschluss"
                    answered={!!field.value}
                  />
                </FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger aria-required="true">
                      <SelectValue placeholder="Bitte auswählen" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {EDUCATION_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <LikertFormItem
            control={form.control}
            name="politicalInterest"
            id="political-interest"
            label="Wie stark interessierst du dich für Politik?"
            leftAnchor="Gar nicht"
            rightAnchor="Sehr stark"
            min={1}
            max={7}
          />

          <FormField
            control={form.control}
            name="aiChatUsageFrequency"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  <LabelWithCheck
                    label="Wie oft nutzt du KI-Chat-Anwendungen wie ChatGPT oder Claude?"
                    answered={!!field.value}
                  />
                </FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl>
                    <SelectTrigger aria-required="true">
                      <SelectValue placeholder="Bitte auswählen" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {AI_CHAT_USAGE_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <LikertFormItem
            control={form.control}
            name="netPromoterScore"
            id="net-promoter-score"
            label="Wie wahrscheinlich ist es, dass du das System, das du gerade genutzt hast, einer Freundin oder einem Freund weiterempfiehlst?"
            leftAnchor="Gar nicht wahrscheinlich"
            rightAnchor="Äußerst wahrscheinlich"
            min={0}
            max={10}
          />
        </div>

        <SubmitButton isSubmitting={isSubmitting} />
      </form>
    </Form>
  );
}
