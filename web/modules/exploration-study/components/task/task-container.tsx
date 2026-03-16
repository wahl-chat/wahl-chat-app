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
import { useCallback, useState } from 'react';
import { TaskTimer } from './task-timer';

export interface TaskContainerProps {
  condition: 'guided' | 'chat';
  durationSeconds: number;
  onEnd: () => Promise<void>;
  children: React.ReactNode;
  className?: string;
}

export function TaskContainer({
  condition,
  durationSeconds,
  onEnd,
  children,
  className,
}: TaskContainerProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [isEnding, setIsEnding] = useState(false);

  const handleTimerEnd = useCallback(async () => {
    setIsEnding(true);
    await onEnd();
  }, [onEnd]);

  const handleManualEnd = useCallback(() => {
    setShowConfirmDialog(true);
  }, []);

  const handleConfirmEnd = useCallback(async () => {
    setShowConfirmDialog(false);
    setIsEnding(true);
    await onEnd();
  }, [onEnd]);

  return (
    <div
      className={cn('relative flex-1 overflow-hidden flex flex-col', className)}
    >
      {/* Task header with timer and end button */}
      <div className="flex items-center justify-between border-b bg-background px-4 py-2">
        <div className="flex items-center gap-3">
          <TaskTimer durationSeconds={durationSeconds} onEnd={handleTimerEnd} />
          <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
            {condition === 'guided' ? 'Geführte Erkundung' : 'Chat-Modus'}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleManualEnd}
          disabled={isEnding}
        >
          {isEnding ? 'Wird beendet...' : 'Aufgabe beenden'}
        </Button>
      </div>

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
    </div>
  );
}
