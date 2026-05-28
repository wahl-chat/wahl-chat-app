'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import VisuallyHidden from '@/components/visually-hidden';
import { cn } from '@/lib/utils';
import { useScreenTelemetry } from '@/modules/exploration-study/hooks/use-screen-telemetry';
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
const POLL_TIMEOUT_MS = 30_000; // give up after 30s of no result

export function QuizDisplay({
  sessionId,
  onSubmit,
  isSubmitting = false,
  className,
}: QuizDisplayProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [pollFailed, setPollFailed] = useState(false);
  const [pollAttempt, setPollAttempt] = useState(0);
  const [hasStarted, setHasStarted] = useState(false);
  const [questions, setQuestions] = useState<QuizQuestionType[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Map<string, QuizAnswer>>(new Map());
  const questionStartTime = useRef<number>(Date.now());

  const currentQuestion = questions[currentIndex];

  // Behavioral integrity telemetry: tab/window focus, copy/paste, cursor
  // jumps — tagged with the question the participant is currently on. Only
  // active once the quiz is interactive (not while polling / on the intro).
  const { recordItemTiming } = useScreenTelemetry(sessionId, 'quiz', {
    enabled: hasStarted && !isLoading,
    getItemId: () => currentQuestion?.id,
  });

  // Record dwell time on the question being left before moving on.
  const recordLeavingItem = useCallback(() => {
    if (!currentQuestion) return;
    recordItemTiming(
      currentQuestion.id,
      Date.now() - questionStartTime.current,
    );
  }, [currentQuestion, recordItemTiming]);

  // Poll for quiz readiness. Times out after POLL_TIMEOUT_MS so a stuck
  // backend doesn't leave the participant on an infinite spinner; the user
  // can then retry via the error UI (which bumps pollAttempt).
  useEffect(() => {
    let cancelled = false;
    let timeoutId: NodeJS.Timeout;
    const pollStartedAt = Date.now();

    const pollQuiz = async () => {
      const response = await studyApi.getQuiz(sessionId);

      if (cancelled) return;

      if (response.data?.isReady && response.data.questions.length > 0) {
        setQuestions(response.data.questions);
        setIsLoading(false);
        questionStartTime.current = Date.now();
        return;
      }

      if (Date.now() - pollStartedAt >= POLL_TIMEOUT_MS) {
        setPollFailed(true);
        setIsLoading(false);
        return;
      }

      timeoutId = setTimeout(pollQuiz, POLL_INTERVAL);
    };

    pollQuiz();

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [sessionId, pollAttempt]);

  const retryPoll = useCallback(() => {
    setPollFailed(false);
    setIsLoading(true);
    setPollAttempt((n) => n + 1);
  }, []);

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
      recordLeavingItem();
      setCurrentIndex((prev) => prev + 1);
      questionStartTime.current = Date.now();
      focusCurrentQuestionHeading();
    }
  }, [
    currentIndex,
    questions.length,
    focusCurrentQuestionHeading,
    recordLeavingItem,
  ]);

  const handlePrevious = useCallback(() => {
    if (currentIndex > 0) {
      recordLeavingItem();
      setCurrentIndex((prev) => prev - 1);
      questionStartTime.current = Date.now();
      focusCurrentQuestionHeading();
    }
  }, [currentIndex, focusCurrentQuestionHeading, recordLeavingItem]);

  const handleSubmit = useCallback(async () => {
    recordLeavingItem();
    const answersArray = Array.from(answers.values());
    await onSubmit(answersArray);
  }, [answers, onSubmit, recordLeavingItem]);

  const currentAnswer = currentQuestion
    ? answers.get(currentQuestion.id)
    : null;
  const allAnswered = answers.size === questions.length;
  const isLastQuestion = currentIndex === questions.length - 1;

  if (pollFailed) {
    return (
      <div
        role="alert"
        className={cn(
          'flex flex-col items-center justify-center space-y-4 py-12 text-center',
          className,
        )}
      >
        <h2 className="text-lg font-medium">
          Das Quiz konnte nicht geladen werden.
        </h2>
        <p className="text-sm text-muted-foreground">
          Bitte versuche es noch einmal. Falls das Problem bestehen bleibt,
          warte einen Moment und versuche es erneut.
        </p>
        <Button onClick={retryPoll}>Erneut versuchen</Button>
      </div>
    );
  }

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
