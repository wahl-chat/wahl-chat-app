'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { studyApi } from '@/modules/exploration-study/services/study-api';
import type {
  QuizAnswer,
  QuizQuestion as QuizQuestionType,
} from '@/modules/exploration-study/types';
import { Loader2 } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { QuizQuestion } from './quiz-question';

export interface QuizDisplayProps {
  sessionId: string;
  onSubmit: (answers: QuizAnswer[]) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

const POLL_INTERVAL = 2000; // 2 seconds

export function QuizDisplay({
  sessionId,
  onSubmit,
  isSubmitting = false,
  className,
}: QuizDisplayProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [questions, setQuestions] = useState<QuizQuestionType[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Map<string, QuizAnswer>>(new Map());
  const questionStartTime = useRef<number>(Date.now());

  // Poll for quiz readiness
  useEffect(() => {
    let cancelled = false;
    let timeoutId: NodeJS.Timeout;

    const pollQuiz = async () => {
      const response = await studyApi.getQuiz(sessionId);

      if (cancelled) return;

      if (response.data?.isReady && response.data.questions.length > 0) {
        setQuestions(response.data.questions);
        setIsLoading(false);
        questionStartTime.current = Date.now();
      } else {
        // Continue polling
        timeoutId = setTimeout(pollQuiz, POLL_INTERVAL);
      }
    };

    pollQuiz();

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [sessionId]);

  const currentQuestion = questions[currentIndex];

  const handleSelect = useCallback(
    (selectedIndex: number) => {
      if (!currentQuestion) return;

      const responseTimeMs = Date.now() - questionStartTime.current;

      setAnswers((prev) => {
        const next = new Map(prev);
        next.set(currentQuestion.id, {
          questionId: currentQuestion.id,
          selectedIndex,
          responseTimeMs,
        });
        return next;
      });
    },
    [currentQuestion],
  );

  const focusCurrentQuestionHeading = useCallback(() => {
    requestAnimationFrame(() => {
      const heading = document.querySelector<HTMLHeadingElement>(
        '[data-quiz-question-heading]',
      );
      heading?.focus();
    });
  }, []);

  const handleNext = useCallback(() => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      questionStartTime.current = Date.now();
      focusCurrentQuestionHeading();
    }
  }, [currentIndex, questions.length, focusCurrentQuestionHeading]);

  const handlePrevious = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex((prev) => prev - 1);
      questionStartTime.current = Date.now();
      focusCurrentQuestionHeading();
    }
  }, [currentIndex, focusCurrentQuestionHeading]);

  const handleSubmit = useCallback(async () => {
    const answersArray = Array.from(answers.values());
    await onSubmit(answersArray);
  }, [answers, onSubmit]);

  const currentAnswer = currentQuestion
    ? answers.get(currentQuestion.id)
    : null;
  const allAnswered = answers.size === questions.length;
  const isLastQuestion = currentIndex === questions.length - 1;

  if (isLoading) {
    return (
      <div
        role="status"
        aria-live="polite"
        className={cn(
          'flex flex-col items-center justify-center space-y-4 py-12',
          className,
        )}
      >
        <Loader2
          aria-hidden="true"
          className="size-8 animate-spin text-foreground"
        />
        <div className="text-center">
          <h2 className="text-lg font-medium">Quiz wird vorbereitet...</h2>
          <p className="text-sm text-foreground">Bitte warte einen Moment.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('space-y-6', className)}>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Wissensquiz</h1>
        <p className="text-sm text-foreground">
          Bitte beantworte die folgenden Fragen basierend auf den Informationen
          aus der vorherigen Aufgabe.
        </p>
      </div>

      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {currentQuestion
          ? `Frage ${currentIndex + 1} von ${questions.length}: ${currentQuestion.question.replace(/\[PARTY_BADGE:([\w-]+)\]/g, '$1')}`
          : ''}
      </div>

      {currentQuestion && (
        <QuizQuestion
          key={currentQuestion.id}
          question={currentQuestion}
          questionNumber={currentIndex + 1}
          totalQuestions={questions.length}
          selectedIndex={currentAnswer?.selectedIndex ?? null}
          onSelect={handleSelect}
        />
      )}

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={handlePrevious}
          disabled={currentIndex === 0}
        >
          Zurück
        </Button>

        <div
          role="status"
          aria-live="polite"
          className="text-sm text-foreground"
        >
          {answers.size} von {questions.length} beantwortet
        </div>

        {isLastQuestion ? (
          <Button
            onClick={handleSubmit}
            disabled={!allAnswered || isSubmitting}
          >
            {isSubmitting ? 'Wird gespeichert...' : 'Absenden'}
          </Button>
        ) : (
          <Button onClick={handleNext} disabled={!currentAnswer}>
            Weiter
          </Button>
        )}
      </div>
    </div>
  );
}
