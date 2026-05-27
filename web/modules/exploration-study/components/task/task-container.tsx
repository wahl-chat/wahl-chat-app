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
  durationSeconds: number;
  /**
   * Server timestamp at which the task was started (ISO string or
   * `Date.parse`-compatible). When provided, the timer anchors to it so the
   * countdown survives page reloads instead of restarting from
   * `durationSeconds`. `null`/`undefined` falls back to the legacy
   * mount-time start.
   */
  startedAt?: string | null;
  /**
   * Ends the task. Resolves `true` once a navigation has been kicked off,
   * `false` on failure — on which the container re-enables its end controls
   * and prompts the participant to retry rather than leaving them stuck.
   */
  onEnd: () => Promise<boolean>;
  /**
   * Fired the moment the countdown reaches zero, before the time-up dialog
   * grabs focus. Used to dismiss any competing modal (e.g. an open leaf
   * panel) so the time-up dialog is the only focus-trapped surface.
   */
  onTimeUp?: () => void;
  /**
   * Telemetry callback fired the first time the user clicks
   * "Aufgabe beenden" — including clicks during the lockout that don't
   * open the confirm dialog. Subsequent clicks are ignored.
   */
  onFirstFinishClick?: () => void;
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
  durationSeconds,
  startedAt,
  onEnd,
  onTimeUp,
  onFirstFinishClick,
  children,
  className,
}: TaskContainerProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [showTimeUpDialog, setShowTimeUpDialog] = useState(false);
  const [isEnding, setIsEnding] = useState(false);
  const [unlockMessage, setUnlockMessage] = useState('');
  // Assertive announcement fired when the clock hits zero. Independent of the
  // dialog's own labelling so the user hears it even if it interrupts a read.
  const [timeUpMessage, setTimeUpMessage] = useState('');
  // Hide the "Freigeschaltet in X:XX" readout until the participant first
  // clicks "Aufgabe beenden". Keeps the clock out of sight during the task
  // while still giving a clear answer when they ask "when can I end?".
  const [unlockCountdownRevealed, setUnlockCountdownRevealed] = useState(false);
  const warningAnnouncerRef = useRef<HTMLDivElement>(null);
  const wasLockedRef = useRef(true);

  const handleTimerEnd = useCallback(() => {
    setShowConfirmDialog(false);
    // Dismiss any competing modal (e.g. an open leaf panel) first, so the
    // time-up dialog becomes the sole focus-trapped surface and focus can't
    // bounce out between two stacked dialogs.
    onTimeUp?.();
    setTimeUpMessage('Die Zeit für diese Aufgabe ist abgelaufen.');
    setShowTimeUpDialog(true);
  }, [onTimeUp]);

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
    startedAt,
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

  const firstFinishClickFiredRef = useRef(false);
  const handleManualEnd = useCallback(() => {
    if (!firstFinishClickFiredRef.current) {
      firstFinishClickFiredRef.current = true;
      onFirstFinishClick?.();
    }
    // While still locked, the first click reveals the unlock countdown
    // rather than opening the confirmation dialog — this is how
    // participants discover "when can I end?" on demand.
    if (!canEnd) {
      setUnlockCountdownRevealed(true);
      return;
    }
    setShowConfirmDialog(true);
  }, [canEnd, onFirstFinishClick]);

  // When the clock hits zero, the leaf panel (if open) is dismissed in the same
  // tick the time-up dialog opens. The leaf Sheet's exit animation keeps its
  // focus scope alive for ~200ms and its unmounting focused element drops focus
  // to <body>, which can leave focus outside the freshly-opened dialog. Force
  // focus onto the dialog's sole action and hold it there for a few frames until
  // the Sheet is gone — Radix's own focus trap keeps it after that. This is the
  // one place we deliberately yank focus: the task is over, it's a hard modal
  // interruption the participant must acknowledge.
  const timeUpContentRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!showTimeUpDialog) return;
    let frame = 0;
    let raf = 0;
    const enforce = () => {
      const dialog = timeUpContentRef.current;
      // Land on the dialog itself, not its button: its accessible name is the
      // title + description, so the screen reader reads what happened before
      // the user reaches the action. Only re-focus if focus has escaped the
      // dialog entirely (don't yank it off the button once the user tabs in).
      if (dialog && !dialog.contains(document.activeElement)) {
        dialog.focus();
      }
      frame += 1;
      // ~20 frames (≈320ms) outlasts the leaf Sheet's 200ms close animation.
      if (frame < 20) raf = requestAnimationFrame(enforce);
    };
    raf = requestAnimationFrame(enforce);
    return () => cancelAnimationFrame(raf);
  }, [showTimeUpDialog]);

  // Re-enable the end controls and prompt a retry when `onEnd` fails, so a
  // network hiccup can't strand the participant on "Wird beendet…" with no
  // way forward — the button itself becomes the retry.
  const endAndHandleFailure = useCallback(async () => {
    setIsEnding(true);
    const ok = await onEnd();
    if (!ok) {
      setIsEnding(false);
      toast.error('Beenden fehlgeschlagen. Bitte versuche es erneut.');
    }
  }, [onEnd]);

  const handleConfirmEnd = useCallback(async () => {
    setShowConfirmDialog(false);
    await endAndHandleFailure();
  }, [endAndHandleFailure]);

  const handleTimeUpContinue = useCallback(async () => {
    await endAndHandleFailure();
  }, [endAndHandleFailure]);

  const secretClickTimestampsRef = useRef<number[]>([]);
  const handleSecretSkipClick = useCallback(async () => {
    const now = Date.now();
    const recent = [...secretClickTimestampsRef.current, now].filter(
      (t) => now - t <= 2000,
    );
    secretClickTimestampsRef.current = recent;
    if (recent.length >= 5) {
      secretClickTimestampsRef.current = [];
      await endAndHandleFailure();
    }
  }, [endAndHandleFailure]);

  // The button is always clickable (unless we're mid-submit). While locked,
  // a click reveals the unlock countdown instead of submitting.
  const endButtonDisabled = isEnding;
  const lockReason = canEnd
    ? 'Du kannst die Aufgabe jetzt beenden.'
    : `Du kannst die Aufgabe erst nach 7 Minuten beenden. Noch ${Math.ceil(secondsUntilUnlock / 60)} Minuten.`;

  return (
    <main
      id="main-content"
      aria-label="Aufgabe"
      tabIndex={-1}
      className={cn(
        'relative flex flex-1 flex-col overflow-hidden focus:outline-none',
        className,
      )}
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
      {/* Time-up announcer — assertive so it interrupts any in-progress read
          the instant the clock hits zero, regardless of where focus is. */}
      <div
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className="sr-only"
      >
        {timeUpMessage}
      </div>

      {/* Task controls: timer and end button. A labelled <section> is a
          navigable region landmark — a <header> nested inside <main> isn't a
          banner and otherwise exposes no landmark to jump to. */}
      <section
        aria-label="Aufgaben-Steuerung"
        className="flex items-center justify-between gap-3 border-b bg-background px-4 py-2"
      >
        <div className="flex items-center gap-3">
          <TaskTimer
            secondsRemaining={secondsRemaining}
            formattedTime={formatTime()}
          />
          <button
            type="button"
            onClick={handleSecretSkipClick}
            aria-hidden="true"
            tabIndex={-1}
            className="size-4 cursor-default border-0 bg-transparent p-0 opacity-0 outline-none focus:outline-none"
          />
        </div>
        <div className="flex items-center gap-2">
          {!canEnd && unlockCountdownRevealed && (
            <span className="text-xs text-foreground">
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
      </section>

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
        <AlertDialogContent
          ref={timeUpContentRef}
          tabIndex={-1}
          // Focus the dialog itself on open (reads the title + description),
          // not Radix's default of the first button.
          onOpenAutoFocus={(e) => {
            e.preventDefault();
            timeUpContentRef.current?.focus();
          }}
          // Keep focus locked in: Escape must not disturb the trap (open is
          // force-controlled, so it can't actually close here either way).
          onEscapeKeyDown={(e) => e.preventDefault()}
        >
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
    </main>
  );
}
