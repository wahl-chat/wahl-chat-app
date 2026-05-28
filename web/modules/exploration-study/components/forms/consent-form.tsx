'use client';

import { Checkbox } from '@/components/ui/checkbox';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import VisuallyHidden from '@/components/visually-hidden';
import { cn } from '@/lib/utils';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import {
  type ConsentFormValues,
  consentSchema,
} from '@/modules/exploration-study/schemas/forms';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';

export interface ConsentFormProps {
  onSubmit: (consentGiven: boolean) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

export function ConsentForm({
  onSubmit,
  isSubmitting = false,
  className,
}: ConsentFormProps) {
  const form = useForm<ConsentFormValues>({
    resolver: zodResolver(consentSchema),
    defaultValues: {
      consentGiven: false,
    },
  });

  const handleSubmit = form.handleSubmit(async (values) => {
    await onSubmit(values.consentGiven);
  });

  return (
    <Form {...form}>
      <form
        onSubmit={handleSubmit}
        aria-labelledby="consent-heading"
        className={cn('space-y-6', className)}
      >
        <div className="space-y-4">
          <h1 id="consent-heading" className="text-2xl font-bold">
            Einwilligungserklärung
          </h1>

          <div className="space-y-6 text-sm text-foreground">
            <p>
              Vielen Dank für dein Interesse an unserer Studie zur Erforschung
              von KI-gestützten Informationssystemen für politische Bildung.
            </p>

            <section className="space-y-2">
              <h2 className="text-lg font-semibold text-foreground">
                Zweck der Studie
              </h2>
              <p>
                Diese Studie untersucht, wie Menschen mit einem KI-System
                interagieren, um politische Informationen zu finden und zu
                verstehen. Deine Teilnahme hilft uns, bessere Systeme für die
                politische Bildung zu entwickeln.
              </p>
            </section>

            <section className="space-y-2">
              <h2 className="text-lg font-semibold text-foreground">
                Ablauf der Studie
              </h2>
              <p>Die Studie führt dich Schritt für Schritt durch fünf Teile:</p>
              <ol className="space-y-0 pt-1">
                {[
                  'Eine kurze Einführung',
                  'Eine Aufgabe zur Informationssuche',
                  'Fragebogen zur Aufgabe',
                  'Ein kurzes Wissensquiz',
                  'Demografische Fragen',
                ].map((step, index, arr) => (
                  <li key={step} className="relative flex gap-3 pb-4 last:pb-0">
                    <VisuallyHidden>({index + 1}) </VisuallyHidden>
                    {index < arr.length - 1 && (
                      <span
                        aria-hidden="true"
                        className="absolute -bottom-1 left-3 top-7 w-px bg-border"
                      />
                    )}
                    <span
                      aria-hidden="true"
                      className="relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full border bg-background text-xs font-semibold text-foreground"
                    >
                      {index + 1}
                    </span>
                    <span className="pt-0.5 text-foreground">{step}</span>
                  </li>
                ))}
              </ol>
            </section>

            <section className="space-y-2">
              <h2 className="text-lg font-semibold text-foreground">
                Datenschutz
              </h2>
              <p>
                Deine Daten werden anonymisiert gespeichert und ausschließlich
                für Forschungszwecke verwendet. Wir erhalten von Prolific eine
                pseudonyme Teilnehmer-ID; deine Identität ist uns nicht bekannt.
              </p>
              <p>
                Um besser zu verstehen, wie du die Aufgabe angehst, erfassen wir
                während der Studie einige grundlegende Verhaltensdaten zur
                Nutzung der Seite.
              </p>
            </section>

            <section className="space-y-2">
              <h2 className="text-lg font-semibold text-foreground">
                Freiwilligkeit
              </h2>
              <p>
                Die Teilnahme ist freiwillig. Du kannst die Studie jederzeit
                ohne Angabe von Gründen abbrechen.
              </p>
            </section>
          </div>
        </div>

        <FormField
          control={form.control}
          name="consentGiven"
          render={({ field }) => (
            <FormItem className="rounded-lg border p-4">
              <div className="flex items-center gap-3">
                <FormControl>
                  <Checkbox
                    checked={field.value === true}
                    onCheckedChange={(checked) =>
                      field.onChange(checked === true)
                    }
                    onBlur={field.onBlur}
                  />
                </FormControl>
                <FormLabel className="cursor-pointer text-sm font-medium leading-none">
                  Ich habe die Informationen gelesen und stimme der Teilnahme zu
                </FormLabel>
              </div>
              <FormDescription className="pl-7">
                Mit dem Setzen des Häkchens bestätigst du, dass du die obigen
                Informationen verstanden hast und freiwillig an der Studie
                teilnimmst.
              </FormDescription>
              <FormMessage className="pl-7" />
            </FormItem>
          )}
        />

        <SubmitButton isSubmitting={isSubmitting} />
      </form>
    </Form>
  );
}
