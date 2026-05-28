'use client';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { studyApi } from '@/modules/exploration-study';
import type { QuizScore } from '@/modules/exploration-study/types';
import { Check, CheckCircle, Copy } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

export default function CompletePage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [feedback, setFeedback] = useState('');
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [quizScore, setQuizScore] = useState<QuizScore | null>(null);
  const [completionCode, setCompletionCode] = useState<string | null>(null);
  const [codeCopied, setCodeCopied] = useState(false);

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

  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    (async () => {
      const response = await studyApi.getProlificCompletionCode(sessionId);
      if (!cancelled && response.data) {
        setCompletionCode(response.data.code);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const handleCopyCode = useCallback(async () => {
    if (!completionCode) return;
    await navigator.clipboard.writeText(completionCode);
    setCodeCopied(true);
    toast.success('Code in die Zwischenablage kopiert!');
    setTimeout(() => setCodeCopied(false), 2000);
  }, [completionCode]);

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
          <div>
            <div className="text-3xl font-bold">
              {quizScore.scorePenalty} / {quizScore.totalQuestions} Punkte
            </div>
            <div className="text-sm text-muted-foreground">
              ({quizScore.totalCorrect} richtig, {quizScore.totalWrong} falsch)
            </div>
          </div>
          <p
            className={
              quizScore.attentionCheckPassed
                ? 'text-sm text-green-700 dark:text-green-400'
                : 'text-sm text-muted-foreground'
            }
          >
            {quizScore.attentionCheckPassed
              ? 'Aufmerksamkeitsprüfung: bestanden ✓'
              : 'Aufmerksamkeitsprüfung: nicht bestanden'}
          </p>
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
          Bei Fragen zur Studie kannst du dich gerne an{' '}
          <a
            href="mailto:paul@wahl.chat"
            className="font-medium text-foreground underline underline-offset-2"
          >
            paul@wahl.chat
          </a>{' '}
          wenden.
        </p>
      </div>

      {completionCode && (
        <div className="space-y-4">
          <Button
            onClick={() => {
              window.location.href = `/api/v1/exploration-study/sessions/${sessionId}/prolific-redirect`;
            }}
            size="lg"
            className="w-full bg-green-600 text-white hover:bg-green-700"
          >
            Studie abschließen und zurück zu Prolific
          </Button>

          <div className="space-y-2 rounded-md border bg-muted/40 p-3 text-left text-xs text-muted-foreground">
            <p>
              Falls die Weiterleitung nicht funktioniert, kannst du diesen Code
              in Prolific eingeben:
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded bg-background px-2 py-1 font-mono text-sm text-foreground">
                {completionCode}
              </code>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleCopyCode}
                aria-label="Code kopieren"
              >
                {codeCopied ? (
                  <Check className="size-4 text-green-600" />
                ) : (
                  <Copy className="size-4" />
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
