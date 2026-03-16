'use client';

import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle } from '@/components/ui/card';
import {
  getRouteForState,
  getStateFromResponse,
  studyApi,
} from '@/modules/exploration-study';
import { Loader2 } from 'lucide-react';
import Image from 'next/image';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

const FAKE_PARTIES = [
  {
    name: 'Merkur',
    abbreviation: 'MER',
    color: 'bg-gray-500',
    image: '/images/merkur.png',
  },
  {
    name: 'Venus',
    abbreviation: 'VEN',
    color: 'bg-amber-400',
    image: '/images/venus.png',
  },
  {
    name: 'Mars',
    abbreviation: 'MAR',
    color: 'bg-red-500',
    image: '/images/mars.png',
  },
  {
    name: 'Jupiter',
    abbreviation: 'JUP',
    color: 'bg-orange-600',
    image: '/images/jupiter.png',
  },
  {
    name: 'Saturn',
    abbreviation: 'SAT',
    color: 'bg-yellow-600',
    image: '/images/saturn.png',
  },
];

export default function TutorialPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;
  const [isSubmitting, setIsSubmitting] = useState(false);

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
    <div className="mx-auto w-full max-w-2xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Einführung</h1>
        <p className="text-sm text-muted-foreground">
          Willkommen zur Studie! Bevor du mit den Aufgaben beginnst, möchten wir
          dir die Parteien vorstellen, die in dieser Studie verwendet werden.
        </p>
      </div>

      <div className="rounded-lg border bg-muted/50 p-4">
        <p className="text-sm">
          <strong>Wichtig:</strong> Die folgenden Parteien sind fiktiv und
          wurden für diese Studie erstellt. Sie entsprechen keinen realen
          politischen Parteien.
        </p>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Die Parteien</h2>

        <div className="grid gap-4">
          {FAKE_PARTIES.map((party) => (
            <Card key={party.abbreviation}>
              <CardHeader className="py-4">
                <div className="flex items-center gap-3">
                  <div className="relative size-10 overflow-hidden rounded-full">
                    <Image
                      src={party.image}
                      alt={`${party.name} Logo`}
                      fill
                      className="object-cover"
                    />
                  </div>
                  <CardTitle className="text-base">{party.name}</CardTitle>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Deine Aufgaben</h2>
        <p className="text-sm text-muted-foreground">
          Du wirst zwei Aufgaben bearbeiten, bei denen du Informationen über die
          Positionen der Parteien zu verschiedenen Themen erkundest. Nach jeder
          Aufgabe wirst du einige Fragen beantworten.
        </p>
        <ul className="list-disc pl-5 text-sm text-muted-foreground">
          <li>Erkunde die Parteipositionen zu den gestellten Themen</li>
          <li>Nimm dir die Zeit, die du benötigst</li>
          <li>Es gibt keine richtigen oder falschen Wege</li>
        </ul>
      </div>

      <Button
        onClick={handleContinue}
        disabled={isSubmitting}
        className="mt-4 w-full"
      >
        {isSubmitting ? (
          <>
            <Loader2 className="mr-2 size-4 animate-spin" />
            Wird geladen...
          </>
        ) : (
          'Aufgaben starten'
        )}
      </Button>
    </div>
  );
}
