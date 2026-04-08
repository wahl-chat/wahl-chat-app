'use client';

import { Checkbox } from '@/components/ui/checkbox';
import { cn } from '@/lib/utils';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import { useState } from 'react';

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
  const [consentGiven, setConsentGiven] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (consentGiven) {
      await onSubmit(consentGiven);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Einwilligungserklärung</h1>

        <div className="prose prose-sm max-w-none space-y-4 text-muted-foreground">
          <p>
            Vielen Dank für dein Interesse an unserer Studie zur Erforschung von
            KI-gestützten Informationssystemen für politische Bildung.
          </p>

          <h2 className="text-lg font-semibold text-foreground">
            Zweck der Studie
          </h2>
          <p>
            Diese Studie untersucht, wie Menschen mit einem KI-System
            interagieren, um politische Informationen zu finden und zu
            verstehen. Deine Teilnahme hilft uns, bessere Systeme für die
            politische Bildung zu entwickeln.
          </p>

          <h2 className="text-lg font-semibold text-foreground">
            Ablauf der Studie
          </h2>
          <p>Die Studie besteht aus folgenden Teilen:</p>
          <ul className="list-disc pl-5">
            <li>Demografische Fragen</li>
            <li>Fragen zu deiner digitalen Kompetenz</li>
            <li>Eine kurze Einführung</li>
            <li>Eine Aufgabe zur Informationssuche</li>
            <li>Fragebogen nach der Aufgabe</li>
          </ul>

          <h2 className="text-lg font-semibold text-foreground">Datenschutz</h2>
          <p>
            Deine Daten werden anonymisiert gespeichert und ausschließlich für
            Forschungszwecke verwendet. Es werden keine personenbezogenen Daten
            erhoben, die Rückschlüsse auf deine Identität ermöglichen.
          </p>

          <h2 className="text-lg font-semibold text-foreground">
            Freiwilligkeit
          </h2>
          <p>
            Die Teilnahme ist freiwillig. Du kannst die Studie jederzeit ohne
            Angabe von Gründen abbrechen.
          </p>
        </div>
      </div>

      <div className="flex items-start gap-3 rounded-lg border p-4">
        <Checkbox
          id="consent"
          checked={consentGiven}
          onCheckedChange={(checked) => setConsentGiven(checked === true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              setConsentGiven(!consentGiven);
            }
          }}
          aria-describedby="consent-description"
        />
        <div className="space-y-1">
          <label
            htmlFor="consent"
            className="cursor-pointer text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Ich habe die Informationen gelesen und stimme der Teilnahme zu
          </label>
          <p id="consent-description" className="text-sm text-muted-foreground">
            Mit dem Setzen des Häkchens bestätigst du, dass du die obigen
            Informationen verstanden hast und freiwillig an der Studie
            teilnimmst.
          </p>
        </div>
      </div>

      <SubmitButton isSubmitting={isSubmitting} disabled={!consentGiven} />
    </form>
  );
}
