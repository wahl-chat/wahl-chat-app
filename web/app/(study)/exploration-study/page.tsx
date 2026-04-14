'use client';

import { Button } from '@/components/ui/button';
import { getRouteForState, studyApi } from '@/modules/exploration-study';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useState } from 'react';

function StudyEntry() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const prolificPid = searchParams.get('PROLIFIC_PID');
  const prolificStudyId = searchParams.get('STUDY_ID');
  const prolificSessionId = searchParams.get('SESSION_ID');

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!prolificPid || !prolificSessionId) {
      setError(
        'Dieser Link ist ungültig. Bitte öffne die Studie über den Link aus Prolific.',
      );
      return;
    }

    let cancelled = false;

    async function create() {
      if (!prolificPid || !prolificSessionId) return;
      const response = await studyApi.createSession({
        prolificPid,
        prolificStudyId,
        prolificSessionId,
      });
      if (cancelled) return;

      if (response.error) {
        setError('Die Sitzung konnte nicht erstellt werden.');
        return;
      }

      if (response.data) {
        router.replace(getRouteForState(response.data.sessionId, 'consent'));
      }
    }

    create();

    return () => {
      cancelled = true;
    };
  }, [prolificPid, prolificStudyId, prolificSessionId, router]);

  if (error) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-4">
        <div className="w-full max-w-md rounded-lg border bg-card p-6 text-center shadow-sm">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="size-6 text-destructive" />
          </div>
          <h1 className="text-xl font-semibold">Zugang nicht möglich</h1>
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
          <Button
            variant="outline"
            className="mt-6 gap-2"
            onClick={() => window.location.reload()}
          >
            <RefreshCw className="size-4" />
            Erneut versuchen
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Studiensitzung wird vorbereitet...
        </p>
      </div>
    </div>
  );
}

export default function StudyEntryPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-dvh items-center justify-center">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <StudyEntry />
    </Suspense>
  );
}
