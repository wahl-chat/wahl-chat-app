'use client';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import { nanoid } from 'nanoid';
import { useCallback, useRef, useState } from 'react';

interface ConversationInputProps {
  onSubmit: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  /** Suggested follow-up questions shown as clickable buttons above the input */
  suggestedQuestions?: string[];
}

/**
 * Chat input for follow-up questions in the leaf view
 */
export function ConversationInput({
  onSubmit,
  disabled = false,
  placeholder = 'Stelle eine Frage...',
  className,
  suggestedQuestions = [],
}: ConversationInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(
    (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      const trimmed = input.trim();
      if (!trimmed || disabled) return;

      onSubmit(trimmed);
      setInput('');
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    },
    [input, disabled, onSubmit],
  );

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter without Shift
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

  return (
    <div className={cn('flex w-full flex-col gap-2', className)}>
      {/* Suggested follow-up questions */}
      {suggestedQuestions.length > 0 && (
        <nav
          aria-label="Vorgeschlagene Rückfragen"
          className="flex flex-wrap gap-2"
        >
          <span className="sr-only">
            Vorgeschlagene Rückfragen. Wählen Sie eine Frage aus, um sie direkt
            zu stellen.
          </span>
          {suggestedQuestions.map((question) => (
            <button
              key={`suggestion-${nanoid()}`}
              type="button"
              onClick={() => handleSuggestionClick(question)}
              disabled={disabled}
              className="rounded-full border border-input bg-background px-3 py-1.5 text-sm text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              aria-label={`Vorgeschlagene Frage: ${question}`}
            >
              {question}
            </button>
          ))}
        </nav>
      )}

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
        />
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
