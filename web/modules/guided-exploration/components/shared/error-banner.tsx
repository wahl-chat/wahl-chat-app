'use client';

import { Button } from '@/components/ui/button';
import { AlertCircle, X } from 'lucide-react';

interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

/**
 * Dismissible error banner that overlays the UI without blocking it.
 */
export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="fixed inset-x-0 top-4 z-50 mx-auto w-full max-w-lg px-4">
      <div className="flex items-start gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4 shadow-lg backdrop-blur-sm">
        <AlertCircle className="mt-0.5 size-5 shrink-0 text-destructive" />
        <div className="flex-1">
          <p className="text-sm font-medium text-destructive">
            Ein Fehler ist aufgetreten
          </p>
          <p className="mt-1 text-sm text-foreground">{message}</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="shrink-0 text-foreground hover:text-foreground"
          onClick={onDismiss}
        >
          <X className="size-4" />
          <span className="sr-only">Schließen</span>
        </Button>
      </div>
    </div>
  );
}
