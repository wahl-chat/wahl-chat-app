'use client';

import { CARD_SURFACE, FOCUS_RING } from '@/components/daily/card-styles';
import { answerStream } from '@/lib/stimmts/chat-answer';
import { chatChips, stimmtsChatHref } from '@/lib/stimmts/chat-chips';
import {
  type ChatTurn,
  answerText,
  appendTurn,
  applyEvent,
  finishTurn,
  isStreaming,
  remainingChips,
  sourcePills,
  toggleTurn,
  turnHistory,
} from '@/lib/stimmts/chat-turns';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { cn, generateUuid } from '@/lib/utils';
import { ArrowRight, ArrowUp, ChevronDown } from 'lucide-react';
import Link from 'next/link';
import { type FormEvent, useEffect, useId, useRef, useState } from 'react';

type Props = {
  puzzle: Puzzle;
  guesses: Guesses;
};

/**
 * Follow-up questions about the day's vote, answered inside the card. Only
 * the latest answer stays open; older ones fold away so the card does not
 * push the result off the screen. "Im Chat weiter" carries the conversation
 * on in the full chat.
 */
function ChatCard({ puzzle, guesses }: Props) {
  const headingId = useId();
  const inputId = useId();
  const latestQuestionRef = useRef<HTMLParagraphElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const nextId = useRef(0);
  const focusQuestion = useRef(false);
  // Set before the first render of a new turn, so a second tap in the same
  // frame cannot start a second answer the way the rendered state would let.
  const busyRef = useRef(false);
  // One conversation per card, as the general chat keys it.
  const [sessionId] = useState(generateUuid);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState('');
  useEffect(() => () => abortRef.current?.abort(), []);

  const streaming = isStreaming(turns);
  const chips = remainingChips(chatChips(puzzle, guesses), turns);
  const latest = turns.at(-1);
  const older = turns.slice(0, -1);

  useEffect(() => {
    if (!focusQuestion.current) return;
    focusQuestion.current = false;
    latestQuestionRef.current?.focus();
  });

  const ask = async (question: string) => {
    const text = question.trim();
    if (!text || busyRef.current) return;
    busyRef.current = true;
    const controller = new AbortController();
    abortRef.current = controller;
    const id = nextId.current++;
    const history = turnHistory(turns);
    setTurns((current) => appendTurn(current, id, text));
    const update = (change: (turn: ChatTurn) => ChatTurn) =>
      setTurns((current) =>
        current.map((turn) => (turn.id === id ? change(turn) : turn)),
      );
    try {
      for await (const event of answerStream(
        { puzzle, sessionId, question: text, history },
        controller.signal,
      )) {
        if (controller.signal.aborted) return;
        update((turn) => applyEvent(turn, event));
      }
    } catch {
      // Falls through to finishTurn, which shows the error line.
    } finally {
      busyRef.current = false;
    }
    // Aborted means the card is gone: there is nothing left to update.
    if (!controller.signal.aborted) update(finishTurn);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (busyRef.current || !draft.trim()) return;
    void ask(draft);
    setDraft('');
  };

  const askChip = (question: string) => {
    if (busyRef.current) return;
    // The chip disappears once asked, so focus goes to the question it
    // asked rather than falling back to the page. Not to the input: on a
    // phone that would open the keyboard over the answer.
    focusQuestion.current = true;
    void ask(question);
  };

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
            aria-expanded={turn.open}
            onClick={() => setTurns((current) => toggleTurn(current, turn.id))}
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
                {turn.open
                  ? 'Antwort ausgeklappt · einklappen'
                  : 'Antwort eingeklappt · anzeigen'}
              </span>
            </span>
            <ChevronDown
              aria-hidden
              className={cn(
                'size-[18px] shrink-0 transition-transform motion-reduce:transition-none',
                turn.open && 'rotate-180',
              )}
            />
          </button>
          {turn.open && <Answer turn={turn} puzzle={puzzle} />}
        </div>
      ))}

      {latest && (
        <>
          <p
            ref={latestQuestionRef}
            tabIndex={-1}
            className="max-w-[85%] self-end rounded-[18px] bg-[var(--daily-surface)] px-3.5 py-[9px] text-[15px] leading-[21px] outline-none"
          >
            {latest.question}
          </p>
          {/* aria-busy holds the announcement until the answer is whole:
              read out word by word, it would be a stutter. */}
          <div
            aria-live="polite"
            aria-busy={latest.status === 'streaming'}
            className="flex flex-col gap-2"
          >
            <Answer turn={latest} puzzle={puzzle} />
            {latest.status === 'streaming' && (
              <span className="text-[13px] text-[var(--daily-muted)]">
                wahl.chat schreibt …
              </span>
            )}
          </div>
          {latest.status === 'done' && (
            <Link
              href={stimmtsChatHref(puzzle, latest.question)}
              className={cn(
                'inline-flex min-h-11 items-center gap-1.5 self-start rounded-sm text-sm font-semibold',
                FOCUS_RING,
              )}
            >
              Im Chat weiter
              <ArrowRight
                aria-hidden
                strokeWidth={2.25}
                className="size-[15px]"
              />
            </Link>
          )}
        </>
      )}

      {chips.length > 0 && (
        <div
          role="group"
          aria-label="Vorgeschlagene Fragen"
          className="mt-0.5 flex flex-wrap gap-2"
        >
          {chips.map((chip) => (
            // aria-disabled rather than disabled while an answer streams: a
            // disabled button drops the focus it holds.
            <button
              key={chip.question}
              type="button"
              aria-disabled={streaming}
              onClick={() => askChip(chip.question)}
              className={cn(
                'inline-flex min-h-11 max-w-full items-center whitespace-normal rounded-[20px] bg-[var(--daily-surface)] px-4 py-2.5 text-left text-sm leading-5 aria-disabled:cursor-not-allowed aria-disabled:opacity-50',
                FOCUS_RING,
              )}
            >
              {chip.label}
            </button>
          ))}
        </div>
      )}

      {/* Sized so the placeholder fits a 375 px screen: below 420 px the
          mark gives up its 28 px to the field, and the send button keeps a
          44 px tap area around its 38 px circle without widening the row. */}
      <form
        onSubmit={submit}
        className="flex items-center gap-2 rounded-full border border-[var(--daily-border)] bg-[var(--daily-canvas)] py-[5px] pl-3.5 pr-[5px] focus-within:ring-2 focus-within:ring-[var(--daily-ink)]"
      >
        <ChatMark />
        <label htmlFor={inputId} className="sr-only">
          Frage zu dieser Abstimmung
        </label>
        {/* 16 px on phones: iOS zooms into any smaller field on focus. */}
        <input
          id={inputId}
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Frage zu dieser Abstimmung …"
          className="h-9 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-[var(--daily-muted)] md:text-[15px]"
        />
        <button
          type="submit"
          aria-label="Frage senden"
          aria-disabled={streaming}
          className={cn(
            "relative inline-flex size-[38px] shrink-0 items-center justify-center rounded-full bg-[var(--daily-ink)] text-[var(--daily-canvas)] after:absolute after:-inset-[3px] after:content-[''] aria-disabled:cursor-not-allowed aria-disabled:opacity-50",
            FOCUS_RING,
          )}
        >
          <ArrowUp aria-hidden strokeWidth={2.5} className="size-[17px]" />
        </button>
      </form>
    </section>
  );
}

function Answer({ turn, puzzle }: { turn: ChatTurn; puzzle: Puzzle }) {
  const text = answerText(turn.answer);
  const { pills, names } = sourcePills(
    turn.status === 'done' ? turn.sources : [],
  );
  return (
    <div className="flex flex-col gap-1.5">
      {(text || turn.status === 'streaming') && (
        <p className="text-[15px] leading-[23px] text-[var(--daily-body)]">
          {text}
          {turn.status === 'streaming' && (
            <span
              aria-hidden
              className="ml-0.5 inline-block h-[17px] w-2 animate-stimmts-blink bg-[var(--daily-ink)] align-[-3px] motion-reduce:hidden"
            />
          )}
        </p>
      )}
      {pills.length > 0 && (
        <ul aria-label="Quellen" className="flex flex-wrap gap-x-1">
          {pills.map((pill) => (
            <li key={pill.url + pill.text} className="max-w-full">
              {/* The visible pill is small; the link around it is a full
                  44 px tap target. */}
              <a
                href={pill.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={pill.label}
                className={cn(
                  'group inline-flex min-h-11 max-w-full items-center rounded-full',
                  FOCUS_RING,
                )}
              >
                <span className="truncate rounded-full bg-[var(--daily-surface)] px-2 py-0.5 text-xs font-medium text-[var(--daily-ink)] group-hover:bg-[var(--daily-border)]">
                  {pill.text}
                </span>
              </a>
            </li>
          ))}
        </ul>
      )}
      {names && (
        <p className="text-[13px] text-[var(--daily-muted)]">
          Quellen: {names}
        </p>
      )}
      {turn.status === 'error' && (
        <p className="text-[13px] text-[var(--daily-muted)]">
          Das hat nicht geklappt.{' '}
          <Link
            href={stimmtsChatHref(puzzle, turn.question)}
            className={cn(
              'inline-flex min-h-11 items-center rounded-sm font-semibold text-[var(--daily-ink)] underline-offset-2 hover:underline',
              FOCUS_RING,
            )}
          >
            Im Chat weiterfragen →
          </Link>
        </p>
      )}
    </div>
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
      className="hidden shrink-0 min-[420px]:block"
    >
      <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
      <path d="m8.5 12 2.5 2.5 4.5-5" stroke="#ed3833" />
    </svg>
  );
}

export default ChatCard;
