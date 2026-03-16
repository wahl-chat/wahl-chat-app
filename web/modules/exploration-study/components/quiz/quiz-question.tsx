'use client';

import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { cn } from '@/lib/utils';
import type { QuizQuestion as QuizQuestionType } from '@/modules/exploration-study/types';

export interface QuizQuestionProps {
  question: QuizQuestionType;
  questionNumber: number;
  totalQuestions: number;
  selectedIndex: number | null;
  onSelect: (index: number) => void;
  className?: string;
}

export function QuizQuestion({
  question,
  questionNumber,
  totalQuestions,
  selectedIndex,
  onSelect,
  className,
}: QuizQuestionProps) {
  return (
    <div className={cn('space-y-4', className)}>
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">
          Frage {questionNumber} von {totalQuestions}
        </p>
        <h2 className="text-lg font-medium">{question.question}</h2>
      </div>

      <RadioGroup
        value={selectedIndex?.toString() ?? ''}
        onValueChange={(value) => onSelect(Number.parseInt(value))}
        className="space-y-3"
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
              {option}
            </span>
          </label>
        ))}
      </RadioGroup>
    </div>
  );
}
