'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import VisuallyHidden from '@/components/visually-hidden';
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
  const [hasStarted, setHasStarted] = useState(false);
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
          <h2 className="text-lg font-medium">Wird vorbereitet...</h2>
          <p className="text-sm text-foreground">Bitte warte einen Moment.</p>
        </div>
      </div>
    );
  }

  if (!hasStarted) {
    return (
      <div className={cn('space-y-6', className)}>
        <VisuallyHidden>
          <h1>Das Gespräch</h1>
        </VisuallyHidden>
        <Card>
          <CardHeader>
            <CardTitle>
              <h2>Deine Freundin trifft ein</h2>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p>
              Deine Freundin trifft jetzt ein und beginnt das Gespräch. Sie
              stellt dir zu jeder Partei eine Frage.
            </p>
            <p>
              Bitte wähle die Antwort, die zu dem passt, was du vorbereitet
              hast. Wenn du dir nicht sicher bist, wähle{' '}
              <strong>„Weiß ich nicht“</strong> — deine Freundin hört das
              lieber, als dass du rätst.
            </p>
            <div className="rounded-md border bg-muted/40 p-3 text-sm">
              <p className="font-medium">So wird gewertet:</p>
              <ul className="mt-1 space-y-0.5">
                <li>
                  Richtige Antwort: <strong>+1 Punkt</strong>
                </li>
                <li>
                  „Weiß ich nicht“: <strong>0 Punkte</strong>
                </li>
                <li>
                  Falsche Antwort: <strong>−1 Punkt</strong>
                </li>
              </ul>
              <p className="mt-2 text-muted-foreground">
                Raten lohnt sich also nicht — „Weiß ich nicht“ ist die bessere
                Wahl, wenn du unsicher bist.
              </p>
            </div>
          </CardContent>
        </Card>
        <Button
          onClick={() => {
            setHasStarted(true);
            questionStartTime.current = Date.now();
            focusCurrentQuestionHeading();
          }}
          size="lg"
          className="w-full"
        >
          Gespräch beginnen
        </Button>
      </div>
    );
  }

  return (
    <div className={cn('space-y-6', className)}>
      <VisuallyHidden>
        <h1>Das Gespräch</h1>
      </VisuallyHidden>

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
