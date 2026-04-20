'use client';

import { Button } from '@/components/ui/button';
import { STUDY_FAKE_PARTIES } from '@/modules/exploration-study';
import { keysToCamelCase } from '@/modules/guided-exploration/utils/case-conversion';
import { AlertCircle, ArrowLeft, Loader2 } from 'lucide-react';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

type PartyClaim = {
  id: string;
  claim: string;
  argument: string;
};

type PartySubtopic = {
  slug: string;
  label: string;
  claims: PartyClaim[];
};

type PartyTopic = {
  slug: string;
  label: string;
  subtopics: PartySubtopic[];
};

type PartyClaims = {
  partyId: string;
  partyName: string;
  topics: PartyTopic[];
};

const HIGHLIGHT_DURATION_MS = 2500;

export default function PartySourcesPage() {
  const params = useParams<{ partyId: string }>();
  const partyId = params.partyId?.toLowerCase() ?? '';
  const party = STUDY_FAKE_PARTIES.find((p) => p.party_id === partyId);

  const [data, setData] = useState<PartyClaims | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!partyId) return;
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(
          `/api/v1/exploration-study/parties/${partyId}/claims`,
        );
        if (!res.ok) {
          if (!cancelled) setError('Die Quellen konnten nicht geladen werden.');
          return;
        }
        const json = await res.json();
        if (cancelled) return;
        setData(keysToCamelCase<PartyClaims>(json));
      } catch {
        if (!cancelled) setError('Die Quellen konnten nicht geladen werden.');
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [partyId]);

  const focusHash = useCallback(() => {
    if (typeof window === 'undefined') return;
    const hash = window.location.hash.slice(1);
    if (!hash) return;

    const el = document.getElementById(hash);
    if (!el) return;

    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.focus({ preventScroll: true });
    el.setAttribute('data-highlight', 'true');
    window.setTimeout(() => {
      el.removeAttribute('data-highlight');
    }, HIGHLIGHT_DURATION_MS);

    const claimNumber = el.getAttribute('data-claim-number');
    const text = el.textContent?.trim() ?? '';
    const preview = text.length > 160 ? `${text.slice(0, 157)}…` : text;
    setAnnouncement(
      claimNumber
        ? `Quelle ${claimNumber} angezeigt: ${preview}`
        : `Quelle angezeigt: ${preview}`,
    );
  }, []);

  useEffect(() => {
    if (!data) return;
    const timer = window.setTimeout(focusHash, 60);
    window.addEventListener('hashchange', focusHash);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('hashchange', focusHash);
    };
  }, [data, focusHash]);

  if (!party) {
    return (
      <ErrorState
        title="Unbekannte Partei"
        message="Diese Partei existiert in der Studie nicht."
      />
    );
  }

  if (error) {
    return <ErrorState title="Quellen nicht verfügbar" message={error} />;
  }

  if (!data) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Quellen werden geladen…
          </p>
        </div>
      </div>
    );
  }

  let claimCounter = 0;

  return (
    <div className="min-h-dvh bg-background" ref={containerRef}>
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {announcement}
      </div>

      <header
        className="sticky top-0 z-10 border-b bg-background/95 backdrop-blur"
        style={{ borderTopColor: party.background_color, borderTopWidth: 4 }}
      >
        <div className="mx-auto flex max-w-3xl items-center gap-4 p-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => window.close()}
            aria-label="Fenster schließen"
          >
            <ArrowLeft className="size-5" />
          </Button>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              Wahlprogramm-Quellen
            </p>
            <h1 className="text-xl font-semibold">{party.long_name}</h1>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8">
        <p className="mb-8 text-sm text-muted-foreground">
          Die folgenden Positionen bilden die Grundlage der Antworten, die du in
          der Studie zu dieser Partei erhältst. Jede Position ist einzeln
          verlinkbar.
        </p>

        <nav aria-label="Themenübersicht" className="mb-10">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Themen
          </h2>
          <ul className="flex flex-col gap-1">
            {data.topics.map((topic) => (
              <li key={topic.slug}>
                <a
                  href={`#topic-${topic.slug}`}
                  className="text-sm text-primary hover:underline"
                >
                  {topic.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex flex-col gap-12">
          {data.topics.map((topic) => (
            <section
              key={topic.slug}
              id={`topic-${topic.slug}`}
              aria-labelledby={`topic-heading-${topic.slug}`}
            >
              <h2
                id={`topic-heading-${topic.slug}`}
                className="mb-6 text-2xl font-bold"
              >
                {topic.label}
              </h2>
              <div className="flex flex-col gap-8">
                {topic.subtopics.map((subtopic) => (
                  <section
                    key={subtopic.slug}
                    id={`subtopic-${topic.slug}-${subtopic.slug}`}
                    aria-labelledby={`subtopic-heading-${topic.slug}-${subtopic.slug}`}
                  >
                    <h3
                      id={`subtopic-heading-${topic.slug}-${subtopic.slug}`}
                      className="mb-3 text-lg font-semibold"
                    >
                      {subtopic.label}
                    </h3>
                    <ol className="flex list-none flex-col gap-3 pl-0">
                      {subtopic.claims.map((claim) => {
                        claimCounter += 1;
                        return (
                          <li
                            key={claim.id}
                            id={claim.id}
                            tabIndex={-1}
                            data-claim-number={claimCounter}
                            className="group scroll-mt-28 rounded-md border bg-card p-4 text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary data-[highlight=true]:border-primary data-[highlight=true]:bg-primary/5 data-[highlight=true]:ring-2 data-[highlight=true]:ring-primary"
                          >
                            <div className="mb-1 text-xs font-medium text-muted-foreground">
                              Quelle {claimCounter}
                            </div>
                            <p>{claim.claim}</p>
                            {claim.argument ? (
                              <details className="mt-3">
                                <summary className="cursor-pointer select-none text-xs font-medium text-muted-foreground hover:text-foreground">
                                  Warum?
                                </summary>
                                <p className="mt-2 text-sm text-muted-foreground">
                                  {claim.argument}
                                </p>
                              </details>
                            ) : null}
                          </li>
                        );
                      })}
                    </ol>
                  </section>
                ))}
              </div>
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}

function ErrorState({ title, message }: { title: string; message: string }) {
  return (
    <div className="flex min-h-dvh items-center justify-center p-4">
      <div className="w-full max-w-md rounded-lg border bg-card p-6 text-center shadow-sm">
        <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-destructive/10">
          <AlertCircle className="size-6 text-destructive" />
        </div>
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}
