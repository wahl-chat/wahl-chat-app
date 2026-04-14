'use client';

import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import {
  type LiteracyData,
  MAILS_SHORT_INTRO,
  MAILS_SHORT_ITEMS,
  type MailsShortData,
  type NewsSource,
} from '@/modules/exploration-study/types';
import { useState } from 'react';

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

const MAILS_SCALE_VALUES = Array.from({ length: 11 }, (_, i) => i); // 0..10

interface MailsRatingRowProps {
  itemId: number;
  itemText: string;
  value: number | null;
  onChange: (value: number) => void;
}

function MailsRatingRow({
  itemId,
  itemText,
  value,
  onChange,
}: MailsRatingRowProps) {
  const groupName = `mails-item-${itemId}`;
  return (
    <div className="space-y-3 rounded-lg border p-4">
      <p className="text-sm font-medium leading-relaxed">
        <span className="mr-2 text-muted-foreground">{itemId}.</span>
        {itemText}
      </p>
      <div
        role="radiogroup"
        aria-label={`Bewertung für Aussage ${itemId}`}
        className="flex flex-wrap items-center gap-1.5"
      >
        {MAILS_SCALE_VALUES.map((v) => {
          const inputId = `${groupName}-${v}`;
          const isSelected = value === v;
          return (
            <label
              key={v}
              htmlFor={inputId}
              className={cn(
                'flex size-9 cursor-pointer items-center justify-center rounded-md border text-sm font-medium transition-colors',
                isSelected
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-input bg-background hover:bg-accent hover:text-accent-foreground',
              )}
            >
              <input
                id={inputId}
                type="radio"
                name={groupName}
                value={v}
                checked={isSelected}
                onChange={() => onChange(v)}
                className="sr-only"
              />
              {v}
            </label>
          );
        })}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>gar nicht ausgeprägt</span>
        <span>(nahezu) perfekt</span>
      </div>
    </div>
  );
}

type MailsAnswers = Partial<Record<keyof MailsShortData, number>>;

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

export function LiteracyForm({
  onSubmit,
  isSubmitting = false,
  className,
}: LiteracyFormProps) {
  const [mailsAnswers, setMailsAnswers] = useState<MailsAnswers>({});
  const [newsConsumption, setNewsConsumption] = useState<NewsSource[]>([]);

  const isMailsComplete = MAILS_KEYS.every(
    (key) => mailsAnswers[key] !== undefined,
  );

  const isValid = isMailsComplete && newsConsumption.length > 0;

  const handleMailsChange = (key: keyof MailsShortData, value: number) => {
    setMailsAnswers((prev) => ({ ...prev, [key]: value }));
  };

  const handleToggleNewsSource = (source: NewsSource) => {
    setNewsConsumption((prev) =>
      prev.includes(source)
        ? prev.filter((s) => s !== source)
        : [...prev, source],
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;

    const mailsShort = MAILS_KEYS.reduce((acc, key) => {
      acc[key] = mailsAnswers[key] as number;
      return acc;
    }, {} as MailsShortData);

    await onSubmit({
      mailsShort,
      newsConsumption,
    });
  };

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-8', className)}>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Digitale Kompetenz</h1>
        <p className="text-sm text-muted-foreground">
          Bitte beantworte die folgenden Fragen zu deinen Fähigkeiten im Umgang
          mit künstlicher Intelligenz und zu deinem Nachrichtenkonsum.
        </p>
      </div>

      <section className="space-y-4">
        <div className="space-y-1">
          <h2 className="text-base font-semibold">
            Fähigkeiten im Umgang mit KI
          </h2>
          <p className="whitespace-pre-line text-sm text-muted-foreground">
            {MAILS_SHORT_INTRO}
          </p>
        </div>
        <div className="space-y-3">
          {MAILS_SHORT_ITEMS.map((item, index) => {
            const key = MAILS_KEYS[index];
            return (
              <MailsRatingRow
                key={item.id}
                itemId={item.id}
                itemText={item.text}
                value={mailsAnswers[key] ?? null}
                onChange={(value) => handleMailsChange(key, value)}
              />
            );
          })}
        </div>
      </section>

      <section className="space-y-3">
        <Label>
          Über welche Quellen informierst du dich über politische Themen?
        </Label>
        <p className="text-sm text-muted-foreground">Mehrfachauswahl möglich</p>
        <div className="space-y-2">
          {NEWS_SOURCE_OPTIONS.map((option) => (
            <div
              key={option.value}
              className="flex items-center gap-3 rounded-lg border p-3"
            >
              <Checkbox
                id={`news-source-${option.value}`}
                checked={newsConsumption.includes(option.value)}
                onCheckedChange={() => handleToggleNewsSource(option.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleToggleNewsSource(option.value);
                  }
                }}
              />
              <Label
                htmlFor={`news-source-${option.value}`}
                className="flex-1 cursor-pointer text-sm font-normal"
              >
                {option.label}
              </Label>
            </div>
          ))}
        </div>
      </section>

      <SubmitButton isSubmitting={isSubmitting} disabled={!isValid} />
    </form>
  );
}
