'use client';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTimer } from '@/modules/exploration-study/hooks';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { TaskTimer } from './task-timer';

export const MIN_TASK_DURATION_SECONDS = 7 * 60;

export interface TaskContainerProps {
  condition: 'guided' | 'chat';
  durationSeconds: number;
  onEnd: () => Promise<void>;
  children: React.ReactNode;
  className?: string;
}

function formatMinutesSeconds(totalSeconds: number): string {
  const clamped = Math.max(0, totalSeconds);
  const minutes = Math.floor(clamped / 60);
  const seconds = clamped % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

export function TaskContainer({
  condition,
  durationSeconds,
  onEnd,
  children,
  className,
}: TaskContainerProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [showTimeUpDialog, setShowTimeUpDialog] = useState(false);
  const [isEnding, setIsEnding] = useState(false);
  const [unlockMessage, setUnlockMessage] = useState('');
  const warningAnnouncerRef = useRef<HTMLDivElement>(null);
  const wasLockedRef = useRef(true);

  const handleTimerEnd = useCallback(() => {
    setShowConfirmDialog(false);
    setShowTimeUpDialog(true);
  }, []);

  const handleWarning = useCallback((seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const message =
      minutes > 0
        ? `Noch ${minutes} Minute${minutes > 1 ? 'n' : ''} verbleibend`
        : `Noch ${seconds} Sekunden verbleibend`;
    if (warningAnnouncerRef.current) {
      warningAnnouncerRef.current.textContent = message;
    }
    toast(message, { duration: 6000 });
  }, []);

  const warningThresholds = useMemo(() => {
    const raw = [Math.floor(durationSeconds / 2), 180, 60];
    return [...new Set(raw)]
      .filter((t) => t > 0 && t < durationSeconds)
      .sort((a, b) => b - a);
  }, [durationSeconds]);

  const { secondsRemaining, formatTime, start } = useTimer({
    durationSeconds,
    onEnd: handleTimerEnd,
    onWarning: handleWarning,
    warningThresholds,
  });

  useEffect(() => {
    start();
  }, [start]);

  const elapsedSeconds = Math.max(0, durationSeconds - secondsRemaining);
  const canEnd = elapsedSeconds >= MIN_TASK_DURATION_SECONDS;
  const secondsUntilUnlock = Math.max(
    0,
    MIN_TASK_DURATION_SECONDS - elapsedSeconds,
  );

  // Announce exactly once when the end-task button unlocks.
  useEffect(() => {
    if (canEnd && wasLockedRef.current) {
      wasLockedRef.current = false;
      setUnlockMessage('Du kannst die Aufgabe jetzt beenden.');
      const timeout = setTimeout(() => setUnlockMessage(''), 2000);
      return () => clearTimeout(timeout);
    }
  }, [canEnd]);

  const handleManualEnd = useCallback(() => {
    setShowConfirmDialog(true);
  }, []);

  const handleConfirmEnd = useCallback(async () => {
    setShowConfirmDialog(false);
    setIsEnding(true);
    await onEnd();
  }, [onEnd]);

  const handleTimeUpContinue = useCallback(async () => {
    setIsEnding(true);
    await onEnd();
  }, [onEnd]);

  const endButtonDisabled = isEnding || !canEnd;
  const lockReason = canEnd
    ? 'Du kannst die Aufgabe jetzt beenden.'
    : `Du kannst die Aufgabe erst nach 7 Minuten beenden. Noch ${Math.ceil(secondsUntilUnlock / 60)} Minuten.`;

  return (
    <div
      className={cn('relative flex-1 overflow-hidden flex flex-col', className)}
    >
      {/* Warning announcer (for time-remaining thresholds) */}
      <div
        ref={warningAnnouncerRef}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      />
      {/* Unlock announcer (fires once when end-task unlocks) */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {unlockMessage}
      </div>

      {/* Task header with timer and end button */}
      <header
        aria-label="Aufgaben-Steuerung"
        className="flex items-center justify-between gap-3 border-b bg-background px-4 py-2"
      >
        <div className="flex items-center gap-3">
          <TaskTimer
            secondsRemaining={secondsRemaining}
            formattedTime={formatTime()}
          />
          <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
            <span className="sr-only">Aktueller Modus: </span>
            {condition === 'guided' ? 'Geführte Erkundung' : 'Chat-Modus'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {!canEnd && (
            <span className="text-xs text-muted-foreground" aria-hidden="true">
              Freigeschaltet in {formatMinutesSeconds(secondsUntilUnlock)}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={handleManualEnd}
            disabled={endButtonDisabled}
            aria-describedby="end-task-reason"
          >
            {isEnding ? 'Wird beendet...' : 'Aufgabe beenden'}
          </Button>
          <span id="end-task-reason" className="sr-only">
            {lockReason}
          </span>
        </div>
      </header>

      {/* Exploration content */}
      <div className="flex flex-1 flex-col overflow-hidden">{children}</div>

      {/* Confirmation dialog */}
      <AlertDialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Aufgabe beenden?</AlertDialogTitle>
            <AlertDialogDescription>
              Möchtest du die Aufgabe wirklich beenden? Du kannst danach nicht
              mehr zu dieser Aufgabe zurückkehren.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Abbrechen</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmEnd}>
              Ja, beenden
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Time-up dialog (no cancel — user must acknowledge to continue) */}
      <AlertDialog open={showTimeUpDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Zeit ist abgelaufen</AlertDialogTitle>
            <AlertDialogDescription>
              Die Zeit für diese Aufgabe ist abgelaufen. Deine Antworten sind
              gespeichert. Bitte fahre mit dem nächsten Schritt fort.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction
              onClick={handleTimeUpContinue}
              disabled={isEnding}
            >
              {isEnding
                ? 'Wird weitergeleitet…'
                : 'Weiter zum nächsten Schritt'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
