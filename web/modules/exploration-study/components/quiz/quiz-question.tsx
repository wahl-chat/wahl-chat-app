'use client';

import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { cn } from '@/lib/utils';
import type { QuizQuestion as QuizQuestionType } from '@/modules/exploration-study/types';
import { PartyBadge } from '@/modules/guided-exploration/components/shared/party-badge';
import { Fragment, type ReactNode } from 'react';

export interface QuizQuestionProps {
  question: QuizQuestionType;
  questionNumber: number;
  totalQuestions: number;
  selectedIndex: number | null;
  onSelect: (index: number) => void;
  className?: string;
}

const PARTY_BADGE_TOKEN = /(\[PARTY_BADGE:[\w-]+\])/g;
const PARTY_BADGE_MATCH = /^\[PARTY_BADGE:([\w-]+)\]$/;

function renderWithPartyBadges(text: string): ReactNode {
  const parts = text.split(PARTY_BADGE_TOKEN);
  return parts.map((part, index) => {
    const match = part.match(PARTY_BADGE_MATCH);
    const key = `${index}:${part}`;
    if (match) {
      return <PartyBadge key={key} party={match[1]} inline />;
    }
    return <Fragment key={key}>{part}</Fragment>;
  });
}

export function QuizQuestion({
  question,
  questionNumber,
  totalQuestions,
  selectedIndex,
  onSelect,
  className,
}: QuizQuestionProps) {
  const headingId = `quiz-question-${question.id}-heading`;
  const metaId = `quiz-question-${question.id}-meta`;
  return (
    <div className={cn('space-y-4', className)}>
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <p id={metaId} className="text-sm text-foreground">
            Frage {questionNumber} von {totalQuestions}
          </p>
          {question.party && <PartyBadge party={question.party} inline />}
        </div>
        <h2
          id={headingId}
          data-quiz-question-heading
          className="text-lg font-medium outline-none"
          tabIndex={-1}
        >
          {renderWithPartyBadges(question.question)}
        </h2>
      </div>

      <RadioGroup
        value={selectedIndex?.toString() ?? ''}
        onValueChange={(value) => onSelect(Number.parseInt(value))}
        className="space-y-3"
        aria-labelledby={headingId}
        aria-describedby={metaId}
      >
        {question.options.map((option, index) => {
          const isDontKnow = index === question.options.length - 1;
          return (
            <div key={`${question.id}-${index}`}>
              {isDontKnow && (
                <div className="my-3 flex items-center gap-3">
                  <div className="h-px flex-1 bg-border" />
                  <span className="text-xs text-foreground">oder</span>
                  <div className="h-px flex-1 bg-border" />
                </div>
              )}
              <label
                htmlFor={`option-${question.id}-${index}`}
                className={cn(
                  'flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors',
                  'hover:border-primary/50 hover:bg-primary/5',
                  selectedIndex === index && 'border-primary bg-primary/5',
                  isDontKnow && 'border-dashed text-foreground',
                )}
              >
                <RadioGroupItem
                  value={index.toString()}
                  id={`option-${question.id}-${index}`}
                  className="mt-0.5"
                />
                <span className="text-sm font-normal leading-relaxed">
                  {renderWithPartyBadges(option)}
                </span>
              </label>
            </div>
          );
        })}
      </RadioGroup>
    </div>
  );
}
