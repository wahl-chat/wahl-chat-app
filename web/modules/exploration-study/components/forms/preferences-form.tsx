'use client';

import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import type {
  ComparisonChoice,
  PreferenceSystem,
  PreferencesData,
} from '@/modules/exploration-study/types';
import { useState } from 'react';

export interface PreferencesFormProps {
  onSubmit: (data: PreferencesData) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

const PREFERENCE_OPTIONS: { value: PreferenceSystem; label: string }[] = [
  { value: 'guided', label: 'Mit Führung' },
  { value: 'baseline', label: 'Ohne Führung' },
  { value: 'no_preference', label: 'Keine Präferenz' },
];

const COMPARISON_OPTIONS: { value: ComparisonChoice; label: string }[] = [
  { value: 'guided', label: 'Mit Führung' },
  { value: 'baseline', label: 'Ohne Führung' },
  { value: 'no_difference', label: 'Kein Unterschied' },
];

export function PreferencesForm({
  onSubmit,
  isSubmitting = false,
  className,
}: PreferencesFormProps) {
  const [preferredSystem, setPreferredSystem] =
    useState<PreferenceSystem | null>(null);
  const [preferenceReason, setPreferenceReason] = useState('');
  const [betterForOverview, setBetterForOverview] =
    useState<ComparisonChoice | null>(null);
  const [betterForDetails, setBetterForDetails] =
    useState<ComparisonChoice | null>(null);
  const [additionalFeedback, setAdditionalFeedback] = useState('');

  const isValid =
    preferredSystem !== null &&
    betterForOverview !== null &&
    betterForDetails !== null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      preferredSystem !== null &&
      betterForOverview !== null &&
      betterForDetails !== null
    ) {
      await onSubmit({
        preferredSystem,
        preferenceReason: preferenceReason || undefined,
        betterForOverview,
        betterForDetails,
        additionalFeedback: additionalFeedback || undefined,
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Deine Präferenzen</h1>
        <p className="text-sm text-muted-foreground">
          Abschließend möchten wir deine Einschätzung der beiden Systeme
          erfahren.
        </p>
      </div>

      <div className="space-y-6">
        <div className="space-y-3">
          <Label>Welches System hast du insgesamt bevorzugt?</Label>
          <RadioGroup
            value={preferredSystem ?? undefined}
            onValueChange={(value) =>
              setPreferredSystem(value as PreferenceSystem)
            }
            className="space-y-2"
          >
            {PREFERENCE_OPTIONS.map((option) => (
              <div key={option.value} className="flex items-center space-x-2">
                <RadioGroupItem
                  value={option.value}
                  id={`preferred-${option.value}`}
                />
                <Label
                  htmlFor={`preferred-${option.value}`}
                  className="cursor-pointer font-normal"
                >
                  {option.label}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </div>

        <div className="space-y-2">
          <Label htmlFor="preference-reason">Warum? (optional)</Label>
          <Textarea
            id="preference-reason"
            value={preferenceReason}
            onChange={(e) => setPreferenceReason(e.target.value)}
            placeholder="Bitte begründe deine Wahl..."
            className="min-h-[80px]"
          />
        </div>

        <div className="space-y-3">
          <Label>
            Welches System war besser geeignet, um einen Überblick zu bekommen?
          </Label>
          <RadioGroup
            value={betterForOverview ?? undefined}
            onValueChange={(value) =>
              setBetterForOverview(value as ComparisonChoice)
            }
            className="space-y-2"
          >
            {COMPARISON_OPTIONS.map((option) => (
              <div key={option.value} className="flex items-center space-x-2">
                <RadioGroupItem
                  value={option.value}
                  id={`overview-${option.value}`}
                />
                <Label
                  htmlFor={`overview-${option.value}`}
                  className="cursor-pointer font-normal"
                >
                  {option.label}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </div>

        <div className="space-y-3">
          <Label>
            Welches System war besser geeignet, um Details zu erfahren?
          </Label>
          <RadioGroup
            value={betterForDetails ?? undefined}
            onValueChange={(value) =>
              setBetterForDetails(value as ComparisonChoice)
            }
            className="space-y-2"
          >
            {COMPARISON_OPTIONS.map((option) => (
              <div key={option.value} className="flex items-center space-x-2">
                <RadioGroupItem
                  value={option.value}
                  id={`details-${option.value}`}
                />
                <Label
                  htmlFor={`details-${option.value}`}
                  className="cursor-pointer font-normal"
                >
                  {option.label}
                </Label>
              </div>
            ))}
          </RadioGroup>
        </div>

        <div className="space-y-2">
          <Label htmlFor="additional-feedback">
            Hast du weiteres Feedback? (optional)
          </Label>
          <Textarea
            id="additional-feedback"
            value={additionalFeedback}
            onChange={(e) => setAdditionalFeedback(e.target.value)}
            placeholder="Dein Feedback..."
            className="min-h-[100px]"
          />
        </div>
      </div>

      <SubmitButton isSubmitting={isSubmitting} disabled={!isValid} />
    </form>
  );
}
