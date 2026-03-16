'use client';

import { Button } from '@/components/ui/button';
import { studyApi } from '@/modules/exploration-study';
import { CheckCircle } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';

export default function CompletePage() {
  const params = useParams();
  const sessionId = params.sessionId as string;
  const [isCompleting, setIsCompleting] = useState(true);

  // Mark study as complete on mount
  useEffect(() => {
    async function completeStudy() {
      await studyApi.completeStudy(sessionId);
      setIsCompleting(false);
    }

    completeStudy();
  }, [sessionId]);

  if (isCompleting) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col items-center justify-center py-12">
        <p className="text-muted-foreground">Studie wird abgeschlossen...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-2xl space-y-8 py-12 text-center">
      <div className="flex justify-center">
        <CheckCircle className="size-16 text-green-500" />
      </div>

      <div className="space-y-2">
        <h1 className="text-3xl font-bold">Vielen Dank!</h1>
        <p className="text-lg text-muted-foreground">
          Du hast die Studie erfolgreich abgeschlossen.
        </p>
      </div>

      <div className="space-y-4 rounded-lg border bg-muted/50 p-6 text-left">
        <h2 className="text-lg font-semibold">Über diese Studie</h2>
        <div className="space-y-3 text-sm text-muted-foreground">
          <p>
            In dieser Studie hast du zwei verschiedene Systeme zur
            Informationssuche über politische Themen verwendet. Ziel der
            Forschung ist es zu verstehen, wie unterschiedliche
            Interaktionsdesigns das Lernen und Verstehen politischer
            Informationen beeinflussen.
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
