'use client';

import { Button } from '@/components/ui/button';
import VisuallyHidden from '@/components/visually-hidden';
import {
  getRouteForState,
  getStateFromResponse,
  studyApi,
  useStudySessionContext,
} from '@/modules/exploration-study';
import { Loader2 } from 'lucide-react';
import Image from 'next/image';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

const FAKE_PARTIES = [
  { name: 'Venus', abbreviation: 'VEN', image: '/images/venus.png' },
  { name: 'Mars', abbreviation: 'MAR', image: '/images/mars.png' },
  { name: 'Saturn', abbreviation: 'SAT', image: '/images/saturn.png' },
];

export default function TutorialPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const session = useStudySessionContext();
  const condition = session.currentCondition ?? null;

  const handleContinue = async () => {
    setIsSubmitting(true);
    const response = await studyApi.completeTutorial(sessionId);
    if (response.error) {
      setIsSubmitting(false);
      return;
    }
    if (response.data) {
      const nextState = getStateFromResponse(response.data);
      if (nextState) {
        router.push(getRouteForState(sessionId, nextState));
      }
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">Einführung</h1>
        <p className="text-sm text-muted-foreground">
          Bevor du mit der Aufgabe startest, eine kurze Übersicht.
        </p>
      </header>

      <section aria-labelledby="parties-heading" className="space-y-3">
        <h2 id="parties-heading" className="text-lg font-semibold">
          Die Parteien
        </h2>
        <p className="text-sm text-muted-foreground">
          Diese drei Parteien sind{' '}
          {/* Styled span, not <strong>: keeps the sentence as one continuous
              screen-reader chunk instead of fragmenting at the emphasis. */}
          <span className="font-semibold text-foreground">fiktiv</span> und
          entsprechen keinen realen politischen Parteien — sie wurden nur für
          diese Studie erstellt.
        </p>
        <ul className="flex flex-wrap gap-2">
          {FAKE_PARTIES.map((party) => (
            <li key={party.abbreviation}>
              <div className="flex items-center gap-2 rounded-full border bg-card px-3 py-1.5">
                <div className="relative size-6 overflow-hidden rounded-full">
                  <Image
                    src={party.image}
                    alt=""
                    fill
                    className="object-cover"
                  />
                </div>
                <span className="text-sm">{party.name}</span>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="task-heading" className="space-y-3">
        <h2 id="task-heading" className="text-lg font-semibold">
          Deine Aufgabe
        </h2>
        <p className="text-sm text-muted-foreground">
          Erkunde die Positionen der drei Parteien zu einem politischen Thema.
          Im Anschluss beantwortest du einige Fragen zu deiner Erfahrung.
        </p>
      </section>

      {condition === 'guided' && (
        <section aria-labelledby="exploration-heading" className="space-y-3">
          <h2 id="exploration-heading" className="text-lg font-semibold">
            So funktioniert die Erkundung
          </h2>
          <p className="text-sm text-muted-foreground">
            Du chattest mit der KI und sie bietet dir passende Erkundungen an,
            in denen du die Parteien-Positionen vergleichen kannst.
          </p>
          <ol className="space-y-0 pt-1 text-sm">
            {[
              'Du chattest mit der KI über ein politisches Thema',
              'Die KI bietet dir eine passende Erkundung an',
              'Du wählst ein Unterthema und siehst die Positionen der Parteien nebeneinander',
              'Im Chat darunter stellst du Rückfragen zu einzelnen Positionen',
              'Schließe ein Unterthema ab, wenn du genug weißt, und wechsle zum nächsten',
              'Jederzeit kannst du zum Chat zurück oder eine weitere Erkundung starten',
            ].map((step, index, arr) => (
              <li key={step} className="relative flex gap-3 pb-4 last:pb-0">
                <VisuallyHidden>({index + 1}) </VisuallyHidden>
                {index < arr.length - 1 && (
                  <span
                    aria-hidden="true"
                    className="absolute -bottom-1 left-3 top-7 w-px bg-border"
                  />
                )}
                <span
                  aria-hidden="true"
                  className="relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full border bg-background text-xs font-semibold text-foreground"
                >
                  {index + 1}
                </span>
                <span className="pt-0.5 text-foreground">{step}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <Button
        onClick={handleContinue}
        disabled={isSubmitting}
        className="w-full"
      >
        {isSubmitting ? (
          <>
            <Loader2 aria-hidden="true" className="mr-2 size-4 animate-spin" />
            Wird geladen...
          </>
        ) : (
          'Aufgabe starten'
        )}
      </Button>
    </div>
  );
}
