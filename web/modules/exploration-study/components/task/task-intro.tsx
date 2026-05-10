'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import VisuallyHidden from '@/components/visually-hidden';
import {
  type StudyCondition,
  type StudyTopic,
  TOPIC_INFO,
} from '@/modules/exploration-study/types';
import { Loader2 } from 'lucide-react';
import { useId, useState } from 'react';

interface TaskIntroProps {
  topic: StudyTopic;
  condition: StudyCondition;
  durationMinutes: number;
  onStart: () => void;
  isStarting?: boolean;
}

export function TaskIntro({
  topic,
  condition,
  durationMinutes,
  onStart,
  isStarting = false,
}: TaskIntroProps) {
  const topicInfo = TOPIC_INFO[topic];
  const isGuided = condition === 'guided';

  const [interventionAck, setInterventionAck] = useState(false);
  const interventionAckId = useId();

  const canStart = (!isGuided || interventionAck) && !isStarting;

  const minutesLabel = `${durationMinutes} Minute${
    durationMinutes === 1 ? '' : 'n'
  }`;

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 p-4">
      <VisuallyHidden>
        <h1>Vorbereitung auf das Gespräch</h1>
      </VisuallyHidden>
      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Deine Aufgabe</h2>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p>
            Stell dir vor, eine gute Freundin von dir möchte bei der
            bevorstehenden Wahl ihre Stimme abgeben und ist sich noch unsicher,
            welche Partei sie wählen soll. Sie hat dich gefragt, was die
            Parteien <strong>Venus</strong>, <strong>Mars</strong> und{' '}
            <strong>Saturn</strong> zum Thema <strong>{topicInfo.title}</strong>{' '}
            sagen.
          </p>
          <p>
            Ihr trefft euch gleich, und sie wird dich zu den Positionen der
            Parteien befragen.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            <h2>Was dich erwartet</h2>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p>
            Du hast jetzt <strong>{minutesLabel}</strong> Zeit, dich mit
            wahl.chat auf dieses Gespräch vorzubereiten.{' '}
            {isGuided
              ? 'Die KI bietet dir passende Erkundungen an, in denen du die Parteipositionen Schritt für Schritt vergleichen kannst.'
              : 'Du chattest frei mit der KI und stellst ihr deine Fragen zu den Parteipositionen.'}
          </p>
          <p>
            Bitte mach dir <strong>keine Notizen</strong> — uns interessiert,
            was du aus dem Gespräch behältst.
          </p>
          <p>
            Nach deiner Vorbereitung beginnt das Gespräch mit deiner Freundin:
            Sie wird dir zu jeder Partei eine Reihe von Fragen stellen.
          </p>
        </CardContent>
      </Card>

      {isGuided && (
        <div className="flex items-start gap-3">
          <Checkbox
            id={interventionAckId}
            checked={interventionAck}
            onCheckedChange={(v) => setInterventionAck(v === true)}
            className="mt-0.5"
          />
          <Label
            htmlFor={interventionAckId}
            className="text-sm font-normal leading-snug"
          >
            Mir ist bewusst, dass ich die KI um strukturierte Erkundungen bitten
            kann, die es mir ermöglichen, die Parteipositionen Schritt für
            Schritt und im Vergleich durchzugehen.
          </Label>
        </div>
      )}

      <Button
        onClick={onStart}
        disabled={!canStart}
        size="lg"
        className="w-full"
      >
        {isStarting ? (
          <>
            <Loader2 aria-hidden="true" className="mr-2 size-4 animate-spin" />
            Wird gestartet...
          </>
        ) : (
          'Aufgabe starten'
        )}
      </Button>
    </div>
  );
}
