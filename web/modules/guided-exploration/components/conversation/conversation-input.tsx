'use client';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import { useCallback, useId, useRef, useState } from 'react';

interface ConversationInputProps {
  onSubmit: (message: string) => void;
  disabled?: boolean;
  /** Reason shown to screen readers when the composer is disabled. */
  disabledReason?: string;
  placeholder?: string;
  className?: string;
  /** Suggested follow-up questions shown as clickable buttons above the input */
  suggestedQuestions?: string[];
  /** Whether follow-up questions are currently being generated */
  isLoadingQuestions?: boolean;
}

/**
 * Chat input for follow-up questions in the leaf view.
 * Suggested questions appear in a horizontally scrollable row.
 */
export function ConversationInput({
  onSubmit,
  disabled = false,
  disabledReason,
  placeholder = 'Stelle eine Frage...',
  className,
  suggestedQuestions = [],
  isLoadingQuestions = false,
}: ConversationInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const disabledReasonId = useId();
  const showDisabledReason = disabled && !!disabledReason;

  const handleSubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const trimmed = input.trim();
      if (!trimmed || disabled) return;

      onSubmit(trimmed);
      setInput('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    },
    [input, disabled, onSubmit],
  );

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const trimmed = input.trim();
      if (trimmed && !disabled) {
        onSubmit(trimmed);
        setInput('');
        if (textareaRef.current) {
          textareaRef.current.style.height = 'auto';
        }
      }
    }
  };

  const handleSuggestionClick = (question: string) => {
    if (!disabled) {
      onSubmit(question);
    }
  };

  const showQuestions = suggestedQuestions.length > 0;
  const showLoading = isLoadingQuestions && !showQuestions;

  return (
    <div className={cn('flex w-full flex-col gap-2', className)}>
      {/* Suggested questions — single scrollable row with fixed height */}
      <div className="h-9" aria-live="polite">
        {showLoading && (
          <div className="flex gap-2 overflow-hidden">
            <Skeleton className="h-8 w-48 shrink-0 rounded-full" />
            <Skeleton className="h-8 w-36 shrink-0 rounded-full" />
          </div>
        )}
        {showQuestions && (
          <nav
            aria-label="Vorgeschlagene Rückfragen"
            className="flex gap-2 overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          >
            <span className="sr-only">
              Vorgeschlagene Rückfragen. Navigiere mit Tab und bestätige mit
              Enter.
            </span>
            {suggestedQuestions.map((question) => (
              <button
                key={question}
                type="button"
                tabIndex={0}
                onClick={() => handleSuggestionClick(question)}
                disabled={disabled}
                className="shrink-0 whitespace-nowrap rounded-full border border-input bg-background px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={`Vorgeschlagene Frage: ${question}`}
              >
                {question}
              </button>
            ))}
          </nav>
        )}
      </div>

      {/* Input form */}
      <form
        onSubmit={handleSubmit}
        className="relative w-full overflow-hidden rounded-[24px] border border-input bg-background transition-colors focus-within:border-ring"
      >
        <textarea
          ref={textareaRef}
          className="w-full resize-none bg-transparent py-3 pl-4 pr-11 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          placeholder={placeholder}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          value={input}
          disabled={disabled}
          maxLength={500}
          rows={1}
          aria-label="Nachricht eingeben"
          aria-describedby={showDisabledReason ? disabledReasonId : undefined}
        />
        {showDisabledReason && (
          <span id={disabledReasonId} className="sr-only">
            {disabledReason}
          </span>
        )}
        <Button
          type="submit"
          disabled={!input.trim().length || disabled}
          size="icon"
          className={cn(
            'absolute bottom-2 right-2 flex size-8 items-center justify-center rounded-full',
          )}
          aria-label="Nachricht senden"
        >
          <ArrowUp className="size-4" />
        </Button>
      </form>
    </div>
  );
}
