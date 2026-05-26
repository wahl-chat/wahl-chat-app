'use client';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { ArrowUp, ChevronDown } from 'lucide-react';
import { Fragment, useCallback, useId, useRef, useState } from 'react';

import { PartyBadge } from '@/modules/guided-exploration/components/shared/party-badge';

const PARTY_BADGE_SPLIT = /(\[PARTY_BADGE:[\w-]+\])/g;
const PARTY_BADGE_MATCH = /^\[PARTY_BADGE:([\w-]+)\]$/;

function renderQuestionWithBadges(question: string): React.ReactNode {
  const parts = question.split(PARTY_BADGE_SPLIT);
  if (parts.length === 1) return question;
  return parts.map((part, i) => {
    const m = part.match(PARTY_BADGE_MATCH);
    const key = `${i}:${part}`;
    if (m) {
      return <PartyBadge key={key} party={m[1]} inline />;
    }
    return <Fragment key={key}>{part}</Fragment>;
  });
}

function questionToPlainText(question: string): string {
  return question.replace(
    /\[PARTY_BADGE:([\w-]+)\]/g,
    (_, party: string) =>
      party.charAt(0).toUpperCase() + party.slice(1).toLowerCase(),
  );
}

interface ConversationInputProps {
  onSubmit: (message: string) => void;
  disabled?: boolean;
  /** Reason shown to screen readers when the composer is disabled. */
  disabledReason?: string;
  placeholder?: string;
  className?: string;
  /**
   * id applied to the textarea so skip-links (e.g. "Zur Chat-Eingabe
   * springen") can move focus directly here.
   */
  inputId?: string;
  /** Suggested follow-up questions shown as clickable buttons above the input */
  suggestedQuestions?: string[];
  /** Whether follow-up questions are currently being generated */
  isLoadingQuestions?: boolean;
  /**
   * Show a small "ask your first question" callout above the composer.
   * Auto-hides once the user types a character.
   */
  showFirstMessageHint?: boolean;
  /** Label for the first-message hint. Defaults to German du-form. */
  firstMessageHintLabel?: string;
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
  inputId,
  suggestedQuestions = [],
  isLoadingQuestions = false,
  showFirstMessageHint = false,
  firstMessageHintLabel = 'Stell hier deine erste Frage',
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
    if (disabled) return;
    onSubmit(questionToPlainText(question));
    // Submitting collapses the suggestions row to its loading state, which
    // unmounts the button the user just clicked. Move focus to the always-
    // mounted textarea first, otherwise focus drops to <body> and a screen
    // reader lands on whichever live region is mid-announcement.
    textareaRef.current?.focus();
  };

  const showQuestions = suggestedQuestions.length > 0;
  const showLoading = isLoadingQuestions && !showQuestions;

  return (
    <div className={cn('relative flex w-full flex-col gap-2', className)}>
      {showFirstMessageHint && (
        // Purely a visual nudge — hidden from screen readers (the textarea's
        // own label already tells SR users this is the message input).
        <div
          aria-hidden="true"
          className={cn(
            'pointer-events-none absolute -top-2 left-1/2 z-10 flex -translate-x-1/2 -translate-y-full flex-col items-center transition-opacity duration-200',
            input.length > 0 ? 'opacity-0' : 'opacity-100',
          )}
        >
          <div className="rounded-full bg-foreground px-6 py-3 text-base font-semibold text-background shadow-lg">
            {firstMessageHintLabel}
          </div>
          <ChevronDown
            aria-hidden="true"
            className="-mt-1 size-6 text-foreground"
            strokeWidth={2.5}
          />
        </div>
      )}
      {/* Suggested questions — single scrollable row, collapses entirely
          when there are no questions and we're not loading. Not a live region:
          announcing the whole list read the follow-ups aloud unprompted on
          open. They stay discoverable via the "Vorgeschlagene Rückfragen"
          landmark and the tab order. */}
      {(showLoading || showQuestions) && (
        <div className="h-9">
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
                  className="inline-flex shrink-0 items-center whitespace-nowrap rounded-full border border-input bg-white px-3 py-1.5 text-sm text-black transition-colors hover:bg-neutral-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label={`Vorgeschlagene Frage: ${questionToPlainText(question)}`}
                >
                  {renderQuestionWithBadges(question)}
                </button>
              ))}
            </nav>
          )}
        </div>
      )}

      {/* Input form */}
      <div className="relative">
        <form
          onSubmit={handleSubmit}
          className="flex w-full flex-col overflow-hidden rounded-[24px] border border-input bg-background transition-colors focus-within:border-ring"
        >
          <textarea
            ref={textareaRef}
            id={inputId}
            className="block w-full resize-none bg-transparent px-4 pt-3 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
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
          <div className="flex justify-end p-2">
            <Button
              type="submit"
              disabled={!input.trim().length || disabled}
              size="icon"
              className="flex size-8 items-center justify-center rounded-full"
              aria-label="Nachricht senden"
            >
              <ArrowUp className="size-4" />
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
