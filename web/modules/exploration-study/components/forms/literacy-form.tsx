'use client';

import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { SliderWithLabels } from '@/modules/exploration-study/components/shared/slider-with-labels';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import type {
  ChatbotUsage,
  LiteracyData,
  NewsSource,
  PoliticalLiteracyAnswers,
} from '@/modules/exploration-study/types';
import { useState } from 'react';

export interface LiteracyFormProps {
  onSubmit: (data: LiteracyData) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

const CHATBOT_USAGE_OPTIONS: { value: ChatbotUsage; label: string }[] = [
  { value: 'never', label: 'Nie' },
  { value: 'rarely', label: 'Selten' },
  { value: 'monthly', label: 'Monatlich' },
  { value: 'weekly', label: 'Wöchentlich' },
  { value: 'daily', label: 'Täglich' },
];

const NEWS_SOURCE_OPTIONS: { value: NewsSource; label: string }[] = [
  { value: 'online', label: 'Online-Nachrichtenseiten' },
  { value: 'tv', label: 'Fernsehen' },
  { value: 'newspaper', label: 'Zeitungen / Zeitschriften' },
  { value: 'social_media', label: 'Soziale Medien' },
  { value: 'radio', label: 'Radio' },
];

interface PoliticalLiteracyQuestion {
  key: keyof PoliticalLiteracyAnswers;
  question: string;
  options: { value: string; label: string }[];
}

const POLITICAL_LITERACY_QUESTIONS: PoliticalLiteracyQuestion[] = [
  {
    key: 'lit_1',
    question: 'Wie viele Stimmen hat man bei der Bundestagswahl?',
    options: [
      { value: '1', label: '1' },
      { value: '2', label: '2' },
      { value: '3', label: '3' },
      { value: '4', label: '4' },
    ],
  },
  {
    key: 'lit_2',
    question: 'Welches Organ wählt den Bundeskanzler?',
    options: [
      { value: 'bundesrat', label: 'Bundesrat' },
      { value: 'bundestag', label: 'Bundestag' },
      { value: 'bundesversammlung', label: 'Bundesversammlung' },
      { value: 'volk', label: 'Volk direkt' },
    ],
  },
  {
    key: 'lit_3',
    question: 'Wie lange dauert eine Legislaturperiode des Bundestags?',
    options: [
      { value: '3', label: '3 Jahre' },
      { value: '4', label: '4 Jahre' },
      { value: '5', label: '5 Jahre' },
      { value: '6', label: '6 Jahre' },
    ],
  },
];

export function LiteracyForm({
  onSubmit,
  isSubmitting = false,
  className,
}: LiteracyFormProps) {
  const [aiFamiliarity, setAiFamiliarity] = useState(4);
  const [chatbotUsage, setChatbotUsage] = useState<ChatbotUsage | ''>('');
  const [newsConsumption, setNewsConsumption] = useState<NewsSource[]>([]);
  const [politicalLiteracyAnswers, setPoliticalLiteracyAnswers] = useState<
    Partial<PoliticalLiteracyAnswers>
  >({});

  const isPoliticalLiteracyComplete =
    politicalLiteracyAnswers.lit_1 !== undefined &&
    politicalLiteracyAnswers.lit_2 !== undefined &&
    politicalLiteracyAnswers.lit_3 !== undefined;

  const isValid =
    chatbotUsage !== '' &&
    newsConsumption.length > 0 &&
    isPoliticalLiteracyComplete;

  const handleToggleNewsSource = (source: NewsSource) => {
    setNewsConsumption((prev) =>
      prev.includes(source)
        ? prev.filter((s) => s !== source)
        : [...prev, source],
    );
  };

  const handlePoliticalLiteracyChange = (
    key: keyof PoliticalLiteracyAnswers,
    value: string,
  ) => {
    setPoliticalLiteracyAnswers((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isValid && isPoliticalLiteracyComplete) {
      await onSubmit({
        aiFamiliarity,
        chatbotUsage: chatbotUsage as ChatbotUsage,
        newsConsumption,
        politicalLiteracyAnswers:
          politicalLiteracyAnswers as PoliticalLiteracyAnswers,
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Digitale Kompetenz</h1>
        <p className="text-sm text-muted-foreground">
          Bitte gib an, wie vertraut du mit den folgenden Themen bist.
        </p>
      </div>

      <div className="space-y-6">
        <SliderWithLabels
          id="ai-familiarity"
          label="Wie vertraut bist du mit KI-Systemen (z.B. ChatGPT, Claude)?"
          value={aiFamiliarity}
          onChange={setAiFamiliarity}
          min={1}
          max={7}
          lowAnchor="Gar nicht"
          highAnchor="Sehr vertraut"
        />

        <div className="space-y-2">
          <Label htmlFor="chatbot-usage">
            Wie häufig nutzt du Chatbots oder KI-Assistenten?
          </Label>
          <Select
            value={chatbotUsage}
            onValueChange={(value) => setChatbotUsage(value as ChatbotUsage)}
          >
            <SelectTrigger id="chatbot-usage">
              <SelectValue placeholder="Bitte auswählen" />
            </SelectTrigger>
            <SelectContent>
              {CHATBOT_USAGE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-3">
          <Label>
            Über welche Quellen informierst du dich über politische Themen?
          </Label>
          <p className="text-sm text-muted-foreground">
            Mehrfachauswahl möglich
          </p>
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
        </div>

        <div className="space-y-4 pt-4 border-t">
          <div className="space-y-1">
            <Label className="text-base font-semibold">
              Politisches Wissen
            </Label>
            <p className="text-sm text-muted-foreground">
              Bitte beantworte die folgenden Fragen.
            </p>
          </div>
          {POLITICAL_LITERACY_QUESTIONS.map((q) => (
            <div key={q.key} className="space-y-2">
              <Label>{q.question}</Label>
              <RadioGroup
                value={politicalLiteracyAnswers[q.key] ?? ''}
                onValueChange={(value) =>
                  handlePoliticalLiteracyChange(q.key, value)
                }
                className="flex flex-wrap gap-4"
              >
                {q.options.map((option) => (
                  <div key={option.value} className="flex items-center gap-2">
                    <RadioGroupItem
                      value={option.value}
                      id={`${q.key}-${option.value}`}
                    />
                    <Label
                      htmlFor={`${q.key}-${option.value}`}
                      className="cursor-pointer font-normal"
                    >
                      {option.label}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>
          ))}
        </div>
      </div>

      <SubmitButton isSubmitting={isSubmitting} disabled={!isValid} />
    </form>
  );
}
