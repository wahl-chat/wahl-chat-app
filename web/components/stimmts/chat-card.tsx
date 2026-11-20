'use client';

import { CARD_SURFACE, FOCUS_RING } from '@/components/daily/card-styles';
import { chatChips, stimmtsChatHref } from '@/lib/stimmts/chat-chips';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { type FormEvent, useId, useState } from 'react';

type Props = {
  puzzle: Puzzle;
  guesses: Guesses;
};

/**
 * Follow-up questions about the day's vote, under the result. The answers
 * come from the general chat, which opens anchored on this vote: the card
 * only collects the question.
 */
function ChatCard({ puzzle, guesses }: Props) {
  const router = useRouter();
  const headingId = useId();
  const inputId = useId();
  const hintId = useId();
  const [draft, setDraft] = useState('');
  const chips = chatChips(puzzle, guesses);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.trim()) return;
    router.push(stimmtsChatHref(puzzle, draft));
  };

  return (
    <section
      aria-labelledby={headingId}
      className={cn(CARD_SURFACE, 'flex flex-col gap-3 p-4')}
    >
      <h2 id={headingId} className="text-[15px] font-semibold">
        Mehr über diese Abstimmung erfahren
      </h2>

      {/* Links, not buttons: they open in a new tab like any other link. */}
      <div
        role="group"
        aria-label="Vorgeschlagene Fragen"
        className="flex flex-wrap gap-2"
      >
        {chips.map((chip) => (
          <Link
            key={chip.question}
            href={stimmtsChatHref(puzzle, chip.question)}
            className={cn(
              'inline-flex min-h-11 max-w-full items-center whitespace-normal rounded-[20px] bg-[var(--daily-surface)] px-4 py-2.5 text-left text-sm leading-5',
              FOCUS_RING,
            )}
          >
            {chip.label}
          </Link>
        ))}
      </div>

      <form
        onSubmit={submit}
        className="flex items-center gap-2.5 rounded-full border border-[var(--daily-border)] bg-[var(--daily-canvas)] py-[5px] pl-3.5 pr-[5px] focus-within:ring-2 focus-within:ring-[var(--daily-ink)]"
      >
        <ChatMark />
        <label htmlFor={inputId} className="sr-only">
          Frage zu dieser Abstimmung
        </label>
        <input
          id={inputId}
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          aria-describedby={hintId}
          placeholder="Frage zu dieser Abstimmung …"
          className="h-11 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-[var(--daily-muted)] md:text-[15px]"
        />
        <button
          type="submit"
          aria-label="Frage senden"
          className={cn(
            'inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-[var(--daily-ink)] text-[var(--daily-canvas)]',
            FOCUS_RING,
          )}
        >
          <ArrowUp aria-hidden strokeWidth={2.5} className="size-[17px]" />
        </button>
      </form>
      <p id={hintId} className="text-xs text-[var(--daily-muted)]">
        Antworten mit Quellen im wahl.chat-Chat
      </p>
    </section>
  );
}

/** The wahl.chat speech bubble with its red tick. */
function ChatMark() {
  return (
    <svg
      aria-hidden
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0"
    >
      <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
      <path d="m8.5 12 2.5 2.5 4.5-5" stroke="#ed3833" />
    </svg>
  );
}

export default ChatCard;
