'use client';

import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  type StudyCondition,
  type StudyTopic,
  TOPIC_INFO,
} from '@/modules/exploration-study/types';
import { Loader2 } from 'lucide-react';

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

  return (
    <div className="mx-auto w-full max-w-2xl space-y-8 p-4">
      <header className="space-y-1">
        <p className="text-sm font-medium text-muted-foreground">
          Deine Aufgabe
        </p>
        <h1 className="text-2xl font-bold">{topicInfo.title}</h1>
      </header>

      <Card className="border bg-card">
        <CardContent className="pt-6">
          <div className="max-w-none [&_blockquote]:rounded-none [&_blockquote]:border-l-4 [&_blockquote]:border-primary [&_blockquote]:bg-transparent [&_blockquote]:px-4 [&_blockquote]:py-2 [&_blockquote]:text-foreground">
            <Markdown onReferenceClick={() => {}}>
              {topicInfo.friendQuestion}
            </Markdown>
          </div>
        </CardContent>
      </Card>

      <section aria-labelledby="notes-heading" className="space-y-2">
        <h2 id="notes-heading" className="text-lg font-semibold">
          Hinweise
        </h2>
        <p className="text-sm text-muted-foreground">
          {condition === 'guided'
            ? 'Du erkundest das Thema gemeinsam mit der KI. Sie bietet dir passende Erkundungen an, in denen du die Parteipositionen Schritt für Schritt vergleichen kannst.'
            : 'Du chattest frei mit der KI und stellst ihr deine Fragen zu den Parteipositionen.'}
        </p>
        <p className="text-sm text-muted-foreground">
          Du hast {durationMinutes} Minuten Zeit — nimm dir so viel davon, wie
          du brauchst, um einen guten Überblick zu bekommen.
        </p>
        <p className="text-sm text-muted-foreground">
          Versuche, die wichtigsten Positionen zu verstehen und Gemeinsamkeiten
          sowie Unterschiede zu erkennen. Im Anschluss beantwortest du ein paar
          Wissensfragen zu den Parteipositionen — sei also so vorbereitet, dass
          du deinem Freund die Standpunkte erklären könntest.
        </p>
      </section>

      <Button
        onClick={onStart}
        disabled={isStarting}
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
