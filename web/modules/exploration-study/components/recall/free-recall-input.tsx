'use client';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { SubmitButton } from '@/modules/exploration-study/components/shared/submit-button';
import { useVoiceInput } from '@/modules/exploration-study/hooks';
import type { RecallData } from '@/modules/exploration-study/types';
import { Mic, MicOff, Square } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

export interface FreeRecallInputProps {
  onSubmit: (data: RecallData) => Promise<void>;
  isSubmitting?: boolean;
  className?: string;
}

export function FreeRecallInput({
  onSubmit,
  isSubmitting = false,
  className,
}: FreeRecallInputProps) {
  const [text, setText] = useState('');
  const [voiceInputUsed, setVoiceInputUsed] = useState(false);

  const {
    isSupported,
    isListening,
    interimTranscript,
    startListening,
    stopListening,
  } = useVoiceInput({
    language: 'de-DE',
    onResult: (transcript) => {
      setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
      setVoiceInputUsed(true);
    },
    onError: () => {
      // Voice input errors are handled silently
    },
  });

  // Combined text: user input + interim speech (shown in real-time)
  const displayText =
    isListening && interimTranscript
      ? text
        ? `${text} ${interimTranscript}`
        : interimTranscript
      : text;

  const handleToggleVoice = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (text.trim()) {
      await onSubmit({
        text: text.trim(),
        voiceInputUsed,
      });
    }
  };

  // Stop listening on unmount
  useEffect(() => {
    return () => {
      if (isListening) {
        stopListening();
      }
    };
  }, [isListening, stopListening]);

  return (
    <form onSubmit={handleSubmit} className={cn('space-y-6', className)}>
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Freie Erinnerung</h1>
        <p className="text-sm text-muted-foreground">
          Bitte beschreibe alles, was dir aus der vorherigen Aufgabe in
          Erinnerung geblieben ist. Schreibe frei und ohne Unterbrechung. Es
          gibt keine richtigen oder falschen Antworten. Du kannst auch die
          Spracheingabe nutzen, um deine Gedanken zu diktieren.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label
            htmlFor="recall-text"
            className="text-sm font-medium leading-none"
          >
            Deine Erinnerungen
          </label>
          {isSupported && (
            <Button
              type="button"
              variant={isListening ? 'destructive' : 'outline'}
              size="sm"
              onClick={handleToggleVoice}
              className="gap-2"
            >
              {isListening ? (
                <>
                  <Square className="size-4" />
                  Aufnahme stoppen
                </>
              ) : (
                <>
                  <Mic className="size-4" />
                  Spracheingabe
                </>
              )}
            </Button>
          )}
        </div>

        <Textarea
          id="recall-text"
          value={displayText}
          onChange={(e) => setText(e.target.value)}
          placeholder="Schreibe hier alles auf, woran du dich erinnerst..."
          className="min-h-[200px] resize-none"
          aria-describedby="recall-help"
          readOnly={isListening}
        />

        {isListening && (
          <div
            className="flex items-center gap-2 text-sm text-destructive"
            role="status"
            aria-live="polite"
          >
            <MicOff className="size-4 animate-pulse" />
            Aufnahme läuft... Sprich frei.
          </div>
        )}

        <p id="recall-help" className="text-xs text-muted-foreground">
          {
            'Tipp: Schreibe alles auf, was dir einfällt - auch wenn es nur Fragmente sind.'
          }
        </p>
      </div>

      <SubmitButton isSubmitting={isSubmitting} disabled={!text.trim()} />
    </form>
  );
}
