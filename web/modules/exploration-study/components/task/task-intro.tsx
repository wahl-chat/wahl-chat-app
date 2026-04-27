'use client';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import {
  type StudyCondition,
  type StudyTopic,
  TOPIC_INFO,
} from '@/modules/exploration-study/types';
import {
  Clock,
  Compass,
  HelpCircle,
  Loader2,
  MessageSquare,
  Quote,
} from 'lucide-react';
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

  const [quizAck, setQuizAck] = useState(false);
  const [interventionAck, setInterventionAck] = useState(false);
  const quizAckId = useId();
  const interventionAckId = useId();

  const allAcknowledged = quizAck && (!isGuided || interventionAck);
  const canStart = allAcknowledged && !isStarting;

  return (
    <div className="mx-auto w-full max-w-2xl space-y-8 p-4">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold">{topicInfo.title}</h1>
        <p className="text-foreground">
          Verschaff dir mit Hilfe der KI einen Überblick über die Positionen der
          Parteien zu diesem Thema.
        </p>
      </header>

      <section
        aria-labelledby="scenario-heading"
        className="relative space-y-4 rounded-xl border bg-muted/40 p-6"
      >
        <Quote
          aria-hidden="true"
          className="absolute right-5 top-5 size-5 text-muted-foreground/40"
        />
        <h2
          id="scenario-heading"
          className="text-xs font-medium uppercase tracking-wide text-muted-foreground"
        >
          Die Frage deines Freundes
        </h2>
        <div className="space-y-3 text-lg font-medium leading-relaxed text-foreground">
          <p>
            Ich möchte mich über die Positionen der Parteien zum Thema{' '}
            <strong>{topicInfo.title}</strong> informieren. Kannst du mir einen
            Überblick geben, was die verschiedenen Parteien dazu sagen?
          </p>
          <p className="text-base text-muted-foreground">
            {topic === 'klimaschutz'
              ? 'Mich interessiert besonders, welche konkreten Maßnahmen sie vorschlagen und wo die Unterschiede liegen.'
              : 'Mich interessiert besonders, welche Maßnahmen sie gegen Ungleichheit und Armut vorschlagen.'}
          </p>
        </div>
      </section>

      <section aria-labelledby="hints-heading" className="space-y-3">
        <h2 id="hints-heading" className="text-lg font-semibold">
          Was dich erwartet
        </h2>
        <ul className="space-y-3">
          <li className="flex gap-3">
            {isGuided ? (
              <Compass
                aria-hidden="true"
                className="mt-0.5 size-5 shrink-0 text-muted-foreground"
              />
            ) : (
              <MessageSquare
                aria-hidden="true"
                className="mt-0.5 size-5 shrink-0 text-muted-foreground"
              />
            )}
            <p className="text-sm text-foreground">
              {isGuided
                ? 'Du erkundest das Thema gemeinsam mit der KI. Sie bietet dir passende Erkundungen an, in denen du die Parteipositionen Schritt für Schritt vergleichen kannst.'
                : 'Du chattest frei mit der KI und stellst ihr deine Fragen zu den Parteipositionen.'}
            </p>
          </li>
          <li className="flex gap-3">
            <Clock
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 text-muted-foreground"
            />
            <p className="text-sm text-foreground">
              Du hast{' '}
              <strong>
                {durationMinutes} Minute{durationMinutes === 1 ? '' : 'n'}
              </strong>{' '}
              Zeit — schau einfach, wie weit du kommst.
            </p>
          </li>
          <li className="flex gap-3 rounded-md border border-amber-200 bg-amber-50 p-3 dark:border-amber-900/50 dark:bg-amber-950/30">
            <HelpCircle
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 text-amber-700 dark:text-amber-400"
            />
            <p className="text-sm text-foreground">
              Im Anschluss folgt ein <strong>kurzes Quiz</strong> zu den
              Inhalten, über die du mit der KI gesprochen hast. Versuche, die
              besprochenen Positionen wirklich zu verstehen — nicht möglichst
              viel Stoff abzuarbeiten.
            </p>
          </li>
        </ul>
      </section>

      <section aria-labelledby="ack-heading" className="space-y-3">
        <h2 id="ack-heading" className="sr-only">
          Bestätigungen
        </h2>
        <div className="flex items-start gap-3">
          <Checkbox
            id={quizAckId}
            checked={quizAck}
            onCheckedChange={(v) => setQuizAck(v === true)}
            className="mt-0.5"
          />
          <Label
            htmlFor={quizAckId}
            className="text-sm font-normal leading-snug text-foreground"
          >
            Mir ist bewusst, dass am Ende ein Quiz zu den Inhalten folgt, die
            ich hier mit der KI erkunde.
          </Label>
        </div>
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
              className="text-sm font-normal leading-snug text-foreground"
            >
              Mir ist bewusst, dass ich die KI um strukturierte Erkundungen
              bitten kann, die es mir ermöglichen, die Parteipositionen Schritt
              für Schritt und im Vergleich durchzugehen.
            </Label>
          </div>
        )}
      </section>

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
