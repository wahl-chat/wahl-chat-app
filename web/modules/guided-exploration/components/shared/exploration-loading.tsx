'use client';

import { Loader2 } from 'lucide-react';

interface ExplorationLoadingProps {
  message?: string;
}

export function ExplorationLoading({
  message = 'Lade Erkundung...',
}: ExplorationLoadingProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-1 flex-col items-center justify-center gap-4"
    >
      <Loader2
        aria-hidden="true"
        className="size-8 animate-spin text-muted-foreground"
      />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
