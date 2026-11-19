'use client';

import { CARD_SURFACE, FOCUS_RING } from '@/components/daily/card-styles';
import { chatChips, stimmtsChatHref } from '@/lib/stimmts/chat-chips';
import { chatQuestion } from '@/lib/stimmts/chat-question';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { cn } from '@/lib/utils';
import { ArrowRight, ArrowUp, ChevronDown, Square } from 'lucide-react';
import Link from 'next/link';
import { type FormEvent, useEffect, useId, useRef, useState } from 'react';

type Turn = {
  /** Keys the turn: the same question can be asked twice. */
  id: number;
  question: string;
  answer: string;
  streaming: boolean;
  /** The player stopped it before it ended. */
  stopped: boolean;
};

/**
 * Stands in for the general chat until it exists: words arrive one by one
 * like a streamed answer, so every state of the card can be tried locally.
 * Nothing leaves the device.
 */
async function* placeholderAnswer(signal: AbortSignal) {
  const words =
    'Hier antwortet bald wahl.chat: kurz, in zwei bis drei Sätzen, und jeder Satz mit Quelle aus Plenarprotokoll oder Drucksache.'.split(
      ' ',
    );
  for (const [i, word] of words.entries()) {
    await new Promise((resolve) => setTimeout(resolve, 70));
    if (signal.aborted) return;
    yield i === 0 ? word : ` ${word}`;
  }
}

type Props = {
  puzzle: Puzzle;
  guesses: Guesses;
};

/**
 * Follow-up questions about the day's vote, under the result. Only the
 * latest answer stays open; older ones fold away so the card does not push
 * the Stimmkarte off the screen.
 */
function ChatCard({ puzzle, guesses }: Props) {
  const headingId = useId();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const nextId = useRef(0);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState('');
  // By turn id, so a fold stays as the player left it when the next answer
  // comes in.
  const [openTurns, setOpenTurns] = useState<Set<number>>(new Set());
  useEffect(() => () => abortRef.current?.abort(), []);

  const streaming = turns.some((turn) => turn.streaming);
  const asked = new Set(turns.map((turn) => turn.question));
  const chips = chatChips(puzzle, guesses).filter(
    (chip) => !asked.has(chip.question),
  );
  const latest = turns.at(-1);
  const older = turns.slice(0, -1);

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || streaming) return;
    const controller = new AbortController();
    abortRef.current = controller;
    const id = nextId.current++;
    setTurns((current) => [
      ...current,
      { id, question: text, answer: '', streaming: true, stopped: false },
    ]);
    const update = (change: (turn: Turn) => Turn) =>
      setTurns((current) =>
        current.map((turn) => (turn.id === id ? change(turn) : turn)),
      );
    try {
      for await (const chunk of placeholderAnswer(controller.signal)) {
        update((turn) => ({ ...turn, answer: turn.answer + chunk }));
      }
    } finally {
      // A stream that throws must not leave the stop button up for good.
      update((turn) => ({
        ...turn,
        streaming: false,
        stopped: controller.signal.aborted,
      }));
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (streaming) return;
    void ask(draft);
    setDraft('');
  };

  const askChip = (question: string) => {
    void ask(question);
    // The chip disappears once asked; the composer is where the player goes
    // on from, so focus does not fall back to the page.
    inputRef.current?.focus();
  };

  const toggle = (id: number) =>
    setOpenTurns((current) => {
      const next = new Set(current);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  // The chat's party filter only fits the question it was built for.
  const asIntended = chatQuestion(puzzle, guesses);
  const continueHref =
    latest && !latest.streaming
      ? stimmtsChatHref(
          puzzle,
          latest.question,
          latest.question === asIntended.text ? asIntended.partyIds : [],
        )
      : null;

  return (
    <section
      aria-labelledby={headingId}
      className={cn(CARD_SURFACE, 'flex flex-col gap-3 p-4')}
    >
      <h2 id={headingId} className="text-[15px] font-semibold">
        Mehr über diese Abstimmung erfahren
      </h2>

      {older.map((turn) => (
        <div key={turn.id} className="flex flex-col gap-3">
          <button
            type="button"
            aria-expanded={openTurns.has(turn.id)}
            onClick={() => toggle(turn.id)}
            className={cn(
              'flex min-h-11 w-full items-center gap-2.5 rounded-[10px] border border-[var(--daily-border)] px-3 py-1.5 text-left',
              FOCUS_RING,
            )}
          >
            <span className="flex min-w-0 flex-1 flex-col gap-px">
              <span className="truncate text-sm font-medium">
                {turn.question}
              </span>
              <span className="text-xs text-[var(--daily-muted)]">
                {openTurns.has(turn.id)
                  ? 'Antwort ausgeklappt · einklappen'
                  : 'Antwort eingeklappt · anzeigen'}
              </span>
            </span>
            <ChevronDown
              aria-hidden
              className={cn(
                'size-[18px] shrink-0 transition-transform motion-reduce:transition-none',
                openTurns.has(turn.id) && 'rotate-180',
              )}
            />
          </button>
          {openTurns.has(turn.id) && <Answer turn={turn} />}
        </div>
      ))}

      {latest && (
        <>
          <p className="max-w-[85%] self-end rounded-[18px] bg-[var(--daily-surface)] px-3.5 py-[9px] text-[15px] leading-[21px]">
            {latest.question}
          </p>
          <div className="flex flex-col gap-2">
            <Answer turn={latest} />
            {latest.streaming && (
              <span className="text-[13px] text-[var(--daily-muted)]">
                wahl.chat schreibt …
              </span>
            )}
          </div>
        </>
      )}

      {/* While it streams, only that it is coming: read word by word, the
          answer would be a stutter. It is announced whole once complete. */}
      <p aria-live="polite" className="sr-only">
        {latest?.streaming
          ? 'wahl.chat schreibt …'
          : latest
            ? `${latest.answer}${latest.stopped ? ' … Antwort gestoppt.' : ''}`
            : ''}
      </p>

      {continueHref && (
        <Link
          href={continueHref}
          className={cn(
            'inline-flex min-h-9 items-center gap-1.5 self-start rounded-sm text-sm font-semibold',
            FOCUS_RING,
          )}
        >
          Im Chat weiter
          <ArrowRight aria-hidden strokeWidth={2.25} className="size-[15px]" />
        </Link>
      )}

      {chips.length > 0 && (
        <div
          role="group"
          aria-label="Vorgeschlagene Fragen"
          className="mt-0.5 flex flex-wrap gap-2"
        >
          {chips.map((chip) => (
            <button
              key={chip.question}
              type="button"
              disabled={streaming}
              onClick={() => askChip(chip.question)}
              className={cn(
                'inline-flex min-h-11 max-w-full items-center whitespace-normal rounded-[20px] bg-[var(--daily-surface)] px-4 py-2.5 text-left text-sm leading-5 disabled:opacity-50',
                FOCUS_RING,
              )}
            >
              {chip.label}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={submit}
        className="flex items-center gap-2.5 rounded-full border border-[var(--daily-border)] bg-[var(--daily-canvas)] py-[5px] pl-3.5 pr-[5px] focus-within:ring-2 focus-within:ring-[var(--daily-ink)]"
      >
        <ChatMark />
        <label htmlFor={inputId} className="sr-only">
          Frage zu dieser Abstimmung
        </label>
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Frage zu dieser Abstimmung …"
          className="h-9 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-[var(--daily-muted)] md:text-[15px]"
        />
        {/* One button that changes role, so focus stays on it when the
            answer ends or is stopped. */}
        <button
          type={streaming ? 'button' : 'submit'}
          aria-label={streaming ? 'Antwort stoppen' : 'Frage senden'}
          onClick={streaming ? () => abortRef.current?.abort() : undefined}
          className={cn(
            'inline-flex size-[38px] shrink-0 items-center justify-center rounded-full bg-[var(--daily-ink)] text-[var(--daily-canvas)]',
            FOCUS_RING,
          )}
        >
          {streaming ? (
            <Square aria-hidden fill="currentColor" className="size-3.5" />
          ) : (
            <ArrowUp aria-hidden strokeWidth={2.5} className="size-[17px]" />
          )}
        </button>
      </form>
    </section>
  );
}

function Answer({ turn }: { turn: Turn }) {
  return (
    <p className="text-[15px] leading-[23px] text-[var(--daily-body)]">
      {turn.answer}
      {turn.streaming && (
        <span
          aria-hidden
          className="ml-0.5 inline-block h-[17px] w-2 bg-[var(--daily-ink)] align-[-3px] motion-safe:animate-pulse"
        />
      )}
      {turn.stopped && (
        <span className="text-[13px] text-[var(--daily-muted)]">
          {turn.answer ? ' … ' : ''}Antwort gestoppt
        </span>
      )}
    </p>
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
