import { CARD_SURFACE } from '@/components/daily/card-styles';
import { BASE_URL } from '@/lib/seo';
import { trackResultShared } from '@/lib/stimmts/analytics';
import { STIMMTS_CHAT_ENABLED } from '@/lib/stimmts/chat-chips';
import { PUZZLES } from '@/lib/stimmts/content';
import { feedDate, partyLabel } from '@/lib/stimmts/labels';
import { periodSeats } from '@/lib/stimmts/logo';
import {
  PERIOD_LENGTH,
  currentWahlperiode,
  dayRecords,
  encodePeriod,
} from '@/lib/stimmts/period';
import { getGame } from '@/lib/stimmts/progress';
import { scorePuzzle } from '@/lib/stimmts/score';
import { buildShareText } from '@/lib/stimmts/share';
import { shareImagePath, sharedResultPath } from '@/lib/stimmts/share-image';
import type { Puzzle, Schedule } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { cn } from '@/lib/utils';
import { Pointer } from 'lucide-react';
import { useReducedMotion } from 'motion/react';
import dynamic from 'next/dynamic';
import { useEffect, useMemo, useRef, useState } from 'react';
import Countdown from './countdown';
import FeedbackPrompt from './feedback-prompt';
import PartyTile from './party-tile';
import PeriodChamber from './period-chamber';
import ShareButton from './share-button';
import Stimmkarte from './stimmkarte';
import StimmtsLogo from './stimmts-logo';
import Urn from './urn';
import { Verdict } from './verdict';
import VoteResultCard from './vote-result-card';

/**
 * Fetched only when the switch is on, so while the general chat does not
 * exist the card and its placeholder answer stay out of the result screen's
 * bundle.
 */
const ChatCard = STIMMTS_CHAT_ENABLED
  ? dynamic(() => import('./chat-card'))
  : () => null;

/**
 * The cast, step by step (see the stimmts-fly, -insert and -fall animations):
 * the card flies to the slot, slides through it, falls onto the pile, and
 * the space it took on the page closes.
 */
const CAST_STEPS = [
  { step: 'flying', ms: 650 },
  { step: 'inserting', ms: 380 },
  { step: 'falling', ms: 600 },
  { step: 'closing', ms: 300 },
] as const;

/**
 * With reduced motion the cast still shows, without anything travelling or
 * zooming: the card fades from the page as it fades into the urn.
 */
const CALM_CAST_STEPS = [{ step: 'fading', ms: 450 }] as const;

type CastStep =
  | (typeof CAST_STEPS)[number]['step']
  | (typeof CALM_CAST_STEPS)[number]['step']
  | null;

type Props = {
  number: number;
  playDate: string;
  puzzle: Puzzle;
  schedule: Schedule;
  /** Stamp the score on with a little bounce (the first time only). */
  stamping: boolean;
  /** Opens the vote: the chamber with every member's vote, without tips. */
  onReview: () => void;
  /** Opens a past day of this Wahlperiode, already turned over. */
  onOpenDay: (number: number) => void;
};

/**
 * The end of the day's puzzle, read top to bottom: the stamped Stimmkarte
 * for the player to cast into the urn, sharing, how the Bundestag actually
 * voted, and the Wahlperiode the urn fills. The card leads, so it is on
 * screen the moment the result opens. Once cast, it is gone, the urn rises
 * into its place, and the countdown and a score card take over from it.
 */
function Result({
  number,
  playDate,
  puzzle,
  schedule,
  stamping,
  onReview,
  onOpenDay,
}: Props) {
  const progress = useProgress((state) => state.progress);
  const castCard = useProgress((state) => state.cast);
  const reduceMotion = useReducedMotion() ?? false;
  // Read once, so a later render cannot cut the stamp's bounce short.
  const [stampOnMount] = useState(stamping);
  const game = getGame(progress, puzzle.id);
  const score = scorePuzzle(puzzle, game.guesses);

  const { cards, period, sharedPeriod } = useMemo(() => {
    const records = dayRecords({
      schedule,
      puzzles: PUZZLES,
      progress,
      throughNumber: number,
    });
    const { days } = currentWahlperiode(records, number, game.cast);
    // The calendar and the image show today in its seat, cast or not.
    const throughToday = currentWahlperiode(records, number, true);
    return {
      cards: days.filter((day) => day.kind === 'played').length,
      period: throughToday,
      sharedPeriod: encodePeriod(throughToday.days),
    };
  }, [schedule, progress, number, game.cast]);

  const cardRef = useRef<HTMLElement>(null);
  const slotRef = useRef<SVGPolygonElement>(null);
  const [castStep, setCastStep] = useState<CastStep>(null);
  const [justCast, setJustCast] = useState(false);
  const castTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => () => castTimers.current.forEach(clearTimeout), []);

  const finishCast = () => {
    castCard(puzzle.id);
    setCastStep(null);
    setJustCast(true);
  };
  const cast = () => {
    const card = cardRef.current;
    const slot = slotRef.current;
    if (castStep) {
      return;
    }
    const play = (
      steps: readonly { step: Exclude<CastStep, null>; ms: number }[],
    ) => {
      let elapsed = 0;
      castTimers.current = steps.map(({ step, ms }) => {
        const timer = setTimeout(() => setCastStep(step), elapsed);
        elapsed += ms;
        return timer;
      });
      castTimers.current.push(setTimeout(finishCast, elapsed));
    };
    if (!card || !slot) {
      finishCast();
      return;
    }
    if (reduceMotion) {
      play(CALM_CAST_STEPS);
      return;
    }
    // Measured, so the card lands on the slot wherever the layout puts it:
    // shrunk to the slot's width, its bottom edge resting just above it.
    const from = card.getBoundingClientRect();
    const to = slot.getBoundingClientRect();
    const scale = to.width / from.width;
    const dx = to.left + to.width / 2 - (from.left + from.width / 2);
    const dy =
      to.top - 2 - (from.height * scale) / 2 - (from.top + from.height / 2);
    card.style.setProperty('--dx', `${Math.round(dx)}px`);
    card.style.setProperty('--dy', `${Math.round(dy)}px`);
    card.style.setProperty('--s', scale.toFixed(4));
    play(CAST_STEPS);
  };
  // From the moment it goes through the slot, today's card is in the urn.
  const cardsInUrn = castStep && castStep !== 'flying' ? cards + 1 : cards;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-10">
        {!game.cast && (
          // The card's space closes once it is in the urn, so the urn rises
          // into its place instead of jumping.
          <div
            className={cn(
              'grid transition-[grid-template-rows,margin] duration-300 ease-out',
              castStep === 'closing'
                ? '-mb-10 grid-rows-[0fr]'
                : 'grid-rows-[1fr]',
            )}
          >
            <div
              className={cn(
                'relative min-h-0',
                castStep === 'closing' && 'overflow-hidden',
              )}
            >
              {!castStep && (
                <span
                  aria-hidden
                  className="pointer-events-none absolute inset-0 animate-stimmts-pulse rounded-xl border-2 border-[var(--daily-ink)] motion-reduce:hidden"
                />
              )}
              <Stimmkarte
                ref={cardRef}
                number={number}
                playDate={playDate}
                title={puzzle.title}
                topic={puzzle.topic}
                score={score.correct}
                verdicts={score.parties}
                stamping={stampOnMount && !reduceMotion}
                onCast={cast}
                className={cn(
                  castStep === 'flying' &&
                    'pointer-events-none z-[5] animate-stimmts-fly',
                  castStep === 'fading' &&
                    'pointer-events-none opacity-0 transition-opacity duration-300',
                  castStep &&
                    castStep !== 'flying' &&
                    castStep !== 'fading' &&
                    'invisible',
                )}
              />
            </div>
          </div>
        )}

        {game.cast && (
          // Once the card, which carries the score, is in the urn.
          <div className="flex flex-col items-center gap-1">
            <StimmtsLogo className="text-[19px]" />
            <Countdown size="compact" />
          </div>
        )}

        <div className="flex flex-col gap-4">
          {/* While the card waits, the urn sits a little lower, leaving the
              hint room between the two. */}
          <div className={cn('relative', !game.cast && 'mt-8')}>
            {!game.cast && !castStep && <CastHint />}
            <Urn
              cards={cardsInUrn}
              casting={
                castStep === 'inserting' || castStep === 'falling'
                  ? castStep
                  : castStep === 'fading'
                    ? 'appearing'
                    : null
              }
              slotRef={slotRef}
            />
          </div>
          {game.cast && (
            <p
              className={cn(
                'text-center text-sm text-[var(--daily-muted)]',
                justCast &&
                  'animate-stimmts-screen [animation-delay:0.5s] motion-reduce:animate-none',
              )}
            >
              <span className="font-display text-2xl font-extrabold tabular-nums text-[var(--daily-ink)]">
                {cards}/{PERIOD_LENGTH}
              </span>{' '}
              Stimmkarten abgegeben
            </p>
          )}
        </div>
      </div>

      {game.cast && (
        // The Stimmkarte showed the score until it went into the urn; from
        // then on this card keeps it on screen.
        <section
          aria-label="Dein Ergebnis"
          aria-live="polite"
          className={cn(
            CARD_SURFACE,
            'flex flex-col gap-3 px-4 py-3.5',
            justCast &&
              'animate-stimmts-screen [animation-delay:0.5s] motion-reduce:animate-none',
          )}
        >
          <p className="flex items-baseline justify-between gap-2">
            <span className="font-display text-[30px] font-extrabold tabular-nums leading-[34px] tracking-[-0.02em]">
              {score.correct} von {score.total}{' '}
              <span className="font-sans text-[15px] font-semibold tracking-normal text-[var(--daily-muted)]">
                richtig
              </span>
            </span>
            <span className="text-[13px] text-[var(--daily-muted)]">
              {feedDate(playDate)}
            </span>
          </p>
          <ul
            aria-label="Deine Tipps je Partei"
            className="grid grid-cols-5 gap-1"
          >
            {score.parties.map((entry) => (
              <li
                key={entry.partyId}
                className="flex flex-col items-center gap-1.5"
              >
                <PartyTile partyId={entry.partyId} size="sm" />
                <span className="sr-only">{partyLabel(entry.partyId)}</span>
                <Verdict
                  correct={entry.correct}
                  className="size-[22px] text-xs"
                />
              </li>
            ))}
          </ul>
        </section>
      )}

      <ShareButton
        text={buildShareText({
          puzzleNumber: number,
          score,
          title: puzzle.title,
          url: `${BASE_URL}${sharedResultPath({ number, score: score.correct, playDate })}`,
        })}
        image={{
          path: shareImagePath('square', {
            number,
            score: score.correct,
            playDate,
            period: sharedPeriod,
          }),
          name: `stimmts-${number}.png`,
        }}
        onShared={(method) => trackResultShared('result', method, number)}
      />
      {/* Shown with the result rather than after the cast: appearing later,
          it would land mid-page and push the vote card down under the
          player's eyes. */}
      <FeedbackPrompt />

      <VoteResultCard puzzle={puzzle} onOpen={onReview} />

      {/* Right under the vote: questions come up while it is on screen. */}
      {STIMMTS_CHAT_ENABLED && (
        <ChatCard puzzle={puzzle} guesses={game.guesses} />
      )}

      <div className="mt-5">
        <div className="relative px-6">
          <PeriodChamber
            seats={periodSeats(period.days, false)}
            complete={period.complete}
            today={number}
            onOpen={onOpenDay}
            className="mx-auto max-w-[300px]"
          />
          <div className="absolute bottom-0 left-1/2 flex -translate-x-1/2 flex-col items-center whitespace-nowrap">
            <span className="font-display text-[30px] font-extrabold tabular-nums leading-[34px] tracking-[-0.02em]">
              Tag {period.day}
            </span>
            <span className="text-xs font-medium text-[var(--daily-muted)]">
              von {PERIOD_LENGTH}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Asks for the tap, once: it pops in under the card with a tapping finger,
 * points up at it, and fades after a few seconds, leaving the card's ripple
 * to keep asking.
 */
function CastHint() {
  return (
    <p
      aria-hidden
      className="pointer-events-none absolute inset-x-0 top-[-54px] z-10 flex animate-stimmts-hint justify-center"
    >
      <span className="relative flex items-center gap-2.5 rounded-full bg-[var(--daily-ink)] py-2.5 pl-3 pr-5 font-display text-[17px] font-bold text-[var(--daily-canvas)] shadow-lg">
        {/* The bubble's tail, pointing up at the card. */}
        <span className="absolute -top-1.5 left-1/2 size-3 -translate-x-1/2 rotate-45 rounded-[2px] bg-[var(--daily-ink)]" />
        <span className="flex size-8 items-center justify-center rounded-full bg-background/15">
          <Pointer
            strokeWidth={2.25}
            className="size-5 animate-stimmts-tap motion-reduce:animate-none"
          />
        </span>
        Stimmkarte einwerfen
      </span>
    </p>
  );
}

export default Result;
