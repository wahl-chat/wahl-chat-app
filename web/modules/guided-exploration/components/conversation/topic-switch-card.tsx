'use client';

import { Button } from '@/components/ui/button';
import { ArrowRight, X } from 'lucide-react';

interface TopicSwitchCardProps {
  message: string;
  onAccept: () => void;
  onDismiss: () => void;
}

/**
 * Inline card suggesting the user switch to a more relevant topic.
 * Shown in the conversation when the routing agent detects a related topic.
 */
export function TopicSwitchCard({
  message,
  onAccept,
  onDismiss,
}: TopicSwitchCardProps) {
  return (
    <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
      <p className="mb-3 text-sm">{message}</p>
      <div className="flex gap-2">
        <Button size="sm" onClick={onAccept} className="gap-1.5">
          <ArrowRight aria-hidden="true" className="size-3.5" />
          Ja, Thema wechseln
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onDismiss}
          className="gap-1.5"
        >
          <X aria-hidden="true" className="size-3.5" />
          Nein, hier bleiben
        </Button>
      </div>
    </div>
  );
}
