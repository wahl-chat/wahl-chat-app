'use client';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { studyApi } from '@/modules/exploration-study';
import type { QuizScore } from '@/modules/exploration-study/types';
import { CheckCircle } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

export default function CompletePage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [feedback, setFeedback] = useState('');
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [quizScore, setQuizScore] = useState<QuizScore | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    (async () => {
      const response = await studyApi.getQuizResult(sessionId);
      if (!cancelled && response.data) {
        setQuizScore(response.data);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handleFeedbackSubmit = async () => {
    if (!feedback.trim()) return;
    setIsSubmitting(true);
    await studyApi.submitFeedback(sessionId, { feedback: feedback.trim() });
    setFeedbackSubmitted(true);
    setIsSubmitting(false);
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-8 py-12 text-center">
      <div className="flex justify-center">
        <CheckCircle aria-hidden="true" className="size-16 text-green-500" />
      </div>

      <div className="space-y-2">
        <h1 className="text-3xl font-bold">Vielen Dank!</h1>
        <p className="text-lg text-muted-foreground">
          Du hast die Studie erfolgreich abgeschlossen.
        </p>
      </div>

      {quizScore && (
        <div className="space-y-3 rounded-lg border bg-muted/50 p-6 text-left">
          <h2 className="text-lg font-semibold">Dein Quiz-Ergebnis</h2>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold">
              {Math.round(quizScore.scorePercentage)}%
            </span>
            <span className="text-sm text-muted-foreground">
              (
              {quizScore.totalCredit.toLocaleString('de-DE', {
                maximumFractionDigits: 1,
              })}{' '}
              von {quizScore.totalQuestions} Punkten — {quizScore.totalCorrect}{' '}
              vollständig richtig)
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            Unter allen Teilnehmenden mit den besten Ergebnissen verlosen wir
            einen <strong>20 € Amazon-Gutschein</strong>. Die Verlosung findet
            nach Abschluss der Studie statt.
          </p>
        </div>
      )}

      <div className="space-y-4 rounded-lg border bg-muted/50 p-6 text-left">
        <h2 className="text-lg font-semibold">Über diese Studie</h2>
        <div className="space-y-3 text-sm text-muted-foreground">
          <p>
            In dieser Studie hast du ein System zur Informationssuche über
            politische Themen verwendet. Ziel der Forschung ist es zu verstehen,
            wie unterschiedliche Interaktionsdesigns das Lernen und Verstehen
            politischer Informationen beeinflussen.
          </p>
          <p>
            <strong>Wichtig:</strong> Die in der Studie verwendeten Parteien und
            ihre Positionen waren vollständig fiktiv. Diese wurden speziell für
            diese Studie erstellt und entsprechen keinen realen politischen
            Parteien oder Positionen.
          </p>
          <p>
            Deine Daten werden anonymisiert gespeichert und ausschließlich für
            wissenschaftliche Forschungszwecke verwendet.
          </p>
        </div>
      </div>

      {!feedbackSubmitted && (
        <div className="space-y-4 rounded-lg border p-6 text-left">
          <h2 id="feedback-heading" className="text-lg font-semibold">
            Hast du noch Anmerkungen? (optional)
          </h2>
          <label htmlFor="feedback-textarea" className="sr-only">
            Anmerkungen zur Studie
          </label>
          <Textarea
            id="feedback-textarea"
            aria-labelledby="feedback-heading"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Teile uns gerne deine Gedanken, Anregungen oder Kritik mit..."
            rows={4}
          />
          <Button
            onClick={handleFeedbackSubmit}
            disabled={!feedback.trim() || isSubmitting}
            variant="outline"
          >
            {isSubmitting ? 'Wird gesendet...' : 'Feedback absenden'}
          </Button>
        </div>
      )}

      <div role="status" aria-live="polite">
        {feedbackSubmitted && (
          <p className="text-sm text-muted-foreground">
            Danke für dein Feedback!
          </p>
        )}
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Kontakt</h2>
        <p className="text-sm text-muted-foreground">
          Bei Fragen zur Studie kannst du dich gerne an das Forschungsteam
          wenden.
        </p>
      </div>

      <Button
        variant="outline"
        onClick={() => {
          window.location.href = '/';
        }}
        className="mt-8"
      >
        Zur Startseite
      </Button>
    </div>
  );
}
