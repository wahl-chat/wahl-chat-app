'use client';

import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  type StudyCondition,
  type StudyTopic,
  TOPIC_INFO,
} from '@/modules/exploration-study/types';
import { Clock, Loader2, MessageCircle, TreePine } from 'lucide-react';

interface TaskIntroProps {
  taskNumber: 1 | 2;
  topic: StudyTopic;
  condition: StudyCondition;
  durationMinutes: number;
  onStart: () => void;
  isStarting?: boolean;
}

export function TaskIntro({
  taskNumber,
  topic,
  condition,
  durationMinutes,
  onStart,
  isStarting = false,
}: TaskIntroProps) {
  const topicInfo = TOPIC_INFO[topic];

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 p-4">
      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">
          Aufgabe {taskNumber} von 2
        </p>
        <h1 className="text-2xl font-bold">{topicInfo.title}</h1>
      </div>

      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="pt-6">
          <div className="max-w-none">
            <Markdown onReferenceClick={() => {}}>
              {topicInfo.friendQuestion}
            </Markdown>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Hinweise zur Bearbeitung</h2>

        <div className="grid gap-3">
          <div className="flex items-start gap-3 rounded-lg border p-4">
            <div className="rounded-full bg-primary/10 p-2">
              {condition === 'guided' ? (
                <TreePine className="size-5 text-primary" />
              ) : (
                <MessageCircle className="size-5 text-primary" />
              )}
            </div>
            <div>
              <p className="font-medium">
                {condition === 'guided' ? 'Geführte Erkundung' : 'Chat-Modus'}
              </p>
              <p className="text-sm text-muted-foreground">
                {condition === 'guided'
                  ? 'Du kannst die Themen über einen strukturierten Themenbaum erkunden und dich durch die verschiedenen Aspekte navigieren.'
                  : 'Du kannst frei mit dem System chatten und Fragen zu den Parteipositionen stellen.'}
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-lg border p-4">
            <div className="rounded-full bg-primary/10 p-2">
              <Clock className="size-5 text-primary" />
            </div>
            <div>
              <p className="font-medium">Zeitrahmen</p>
              <p className="text-sm text-muted-foreground">
                Du hast {durationMinutes} Minuten Zeit, um die Informationen zu
                erkunden. Nimm dir die Zeit, die du brauchst, um einen guten
                Überblick zu bekommen.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-lg border bg-muted/50 p-4">
        <p className="text-sm text-muted-foreground">
          <strong>Tipp:</strong> Versuchen Sie, die wichtigsten Positionen der
          Parteien zu verstehen und Gemeinsamkeiten sowie Unterschiede zu
          identifizieren. Im Anschluss wirst du einige Fragen zu den Inhalten
          beantworten.
        </p>
      </div>

      <Button
        onClick={onStart}
        disabled={isStarting}
        size="lg"
        className="mt-4 w-full"
      >
        {isStarting ? (
          <>
            <Loader2 className="mr-2 size-4 animate-spin" />
            Wird gestartet...
          </>
        ) : (
          'Aufgabe starten'
        )}
      </Button>
    </div>
  );
}
