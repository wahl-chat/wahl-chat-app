'use client';

import { Button } from '@/components/ui/button';
import type { SessionMessage } from '@/modules/guided-exploration/types';
import { ArrowRight, Compass } from 'lucide-react';
import { useId, useMemo } from 'react';

interface ExplorationCardProps {
  message: SessionMessage;
  onEnter: (explorationId: string) => void;
  isLoading?: boolean;
}

export function ExplorationCard({
  message,
  onEnter,
  isLoading = false,
}: ExplorationCardProps) {
  const explorationId = useMemo(
    () => message.explorationId,
    [message.explorationId],
  );
  const headingId = useId();
  const query = message.explorationQuery || message.content || '';

  if (!explorationId) {
    return null;
  }

  return (
    <article
      aria-labelledby={headingId}
      className="rounded-lg border bg-card p-4"
    >
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <Compass aria-hidden="true" className="size-5 text-primary" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 id={headingId} className="text-sm font-medium">
            Erkundung bereit{query ? `: ${query}` : ''}
          </h3>
          <p className="mt-1 text-sm text-foreground">
            Du kannst die Parteien-Positionen jetzt im Überblick vergleichen.
          </p>
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <Button
          variant="default"
          size="sm"
          onClick={() => onEnter(explorationId)}
          disabled={isLoading}
          aria-label={query ? `Erkundung öffnen: ${query}` : 'Erkundung öffnen'}
        >
          Erkundung öffnen
          <ArrowRight aria-hidden="true" className="ml-2 size-4" />
        </Button>
      </div>
    </article>
  );
}
