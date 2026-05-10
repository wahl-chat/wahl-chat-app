'use client';

import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { cn } from '@/lib/utils';
import type { QuizQuestion as QuizQuestionType } from '@/modules/exploration-study/types';
import { PartyBadge } from '@/modules/guided-exploration/components/shared/party-badge';
import { Fragment, type ReactNode } from 'react';

const PARTY_BADGE_TOKEN = /(\[PARTY_BADGE:[\w-]+\])/gi;
const PARTY_BADGE_MATCH = /^\[PARTY_BADGE:([\w-]+)\]$/i;

const DONT_KNOW_INDEX = -1;

export interface QuizQuestionProps {
  question: QuizQuestionType;
  questionNumber: number;
  totalQuestions: number;
  selectedIndex: number | null;
  onSelect: (index: number) => void;
  className?: string;
}

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
  const dontKnowId = `option-${question.id}-dont-know`;
  const isDontKnowSelected = selectedIndex === DONT_KNOW_INDEX;
  return (
    <div className={cn('space-y-4', className)}>
      <div className="space-y-2">
        <p id={metaId} className="text-sm text-foreground">
          Frage {questionNumber} von {totalQuestions}
        </p>
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
        value={selectedIndex !== null ? selectedIndex.toString() : ''}
        onValueChange={(value) => onSelect(Number.parseInt(value))}
        className="space-y-3"
        aria-labelledby={headingId}
        aria-describedby={metaId}
      >
        {question.options.map((option, index) => (
          <label
            key={`${question.id}-${index}`}
            htmlFor={`option-${question.id}-${index}`}
            className={cn(
              'flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors',
              'hover:border-primary/50 hover:bg-primary/5',
              selectedIndex === index && 'border-primary bg-primary/5',
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
        ))}

        <div className="my-3 flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="text-xs text-foreground">oder</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        <label
          htmlFor={dontKnowId}
          className={cn(
            'flex cursor-pointer items-start gap-3 rounded-lg border border-dashed p-4 text-foreground transition-colors',
            'hover:border-primary/50 hover:bg-primary/5',
            isDontKnowSelected && 'border-primary bg-primary/5',
          )}
        >
          <RadioGroupItem
            value={DONT_KNOW_INDEX.toString()}
            id={dontKnowId}
            className="mt-0.5"
          />
          <span className="text-sm font-normal leading-relaxed">
            Weiß ich nicht
          </span>
        </label>
      </RadioGroup>
    </div>
  );
}
