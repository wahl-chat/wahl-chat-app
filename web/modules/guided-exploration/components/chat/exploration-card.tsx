'use client';

import { Button } from '@/components/ui/button';
import type { SessionMessage } from '@/modules/guided-exploration/types';
import { ArrowRight, Compass } from 'lucide-react';
import { useMemo } from 'react';

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

  if (!explorationId) {
    return null;
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <Compass aria-hidden="true" className="size-5 text-primary" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">Erkundung gestartet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            {message.explorationQuery || message.content}
          </p>
        </div>
      </div>
      <div className="mt-4 flex justify-end">
        <Button
          variant="default"
          size="sm"
          onClick={() => onEnter(explorationId)}
          disabled={isLoading}
        >
          Erkundung öffnen
          <ArrowRight aria-hidden="true" className="ml-2 size-4" />
        </Button>
      </div>
    </div>
  );
}
