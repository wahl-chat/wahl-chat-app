'use client';

import { Button } from '@/components/ui/button';
import {
  StudyLayout,
  type StudySession,
  getRouteForState,
  getStateFromResponse,
  studyApi,
} from '@/modules/exploration-study';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

export default function StudySessionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const pathname = usePathname();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  const [session, setSession] = useState<StudySession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Refetch session on every pathname change
  useEffect(() => {
    let cancelled = false;

    async function loadSession() {
      setIsLoading(true);
      const response = await studyApi.getSession(sessionId);

      if (cancelled) return;

      if (response.error) {
        setError(response.error);
        setSession(null);
        setIsLoading(false);
      } else if (response.data) {
        setSession(response.data);

        // Redirect to correct page if needed
        const currentState = getStateFromResponse(response.data);
        if (currentState) {
          const expectedPath = getRouteForState(sessionId, currentState);

          if (pathname !== expectedPath) {
            router.replace(expectedPath);
            // Keep loading state until redirect completes
          } else {
            setIsLoading(false);
          }
        } else {
          setIsLoading(false);
        }
      }
    }

    loadSession();

    return () => {
      cancelled = true;
    };
  }, [sessionId, pathname, router]);

  if (isLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Wird geladen...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-4">
        <div className="w-full max-w-md rounded-lg border bg-card p-6 text-center shadow-sm">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/10">
            <AlertCircle className="size-6 text-destructive" />
          </div>
          <h1 className="text-xl font-semibold">Ein Fehler ist aufgetreten</h1>
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

  if (!session) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Studie nicht gefunden</h1>
          <p className="mt-2 text-muted-foreground">
            Die angegebene Studien-ID existiert nicht.
          </p>
        </div>
      </div>
    );
  }

  // For task pages, hide the header and let the task component handle layout
  const isTaskPage = pathname.endsWith('/task');

  return (
    <StudyLayout state={session.state} hideHeader={isTaskPage}>
      {children}
    </StudyLayout>
  );
}
