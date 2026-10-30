import { BASE_URL } from '@/lib/seo';
import { PUZZLES } from '@/lib/stimmts/content';
import { partyLabel } from '@/lib/stimmts/labels';
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
import { useEffect, useMemo, useRef, useState } from 'react';
import Countdown from './countdown';
import OutcomeCard from './outcome-card';
import PartyTile from './party-tile';
import PeriodChamber from './period-chamber';
import ShareButton from './share-button';
import Stimmkarte from './stimmkarte';
import StimmtsLogo from './stimmts-logo';
import Urn from './urn';
import { Verdict } from './verdict';

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
  /** Whether a past day's puzzle can be shown (it may not be released). */
  canOpenDay: (number: number) => boolean;
};

/**
 * The end of the day's puzzle, top to bottom: the stamped Stimmkarte, which
 * the player casts into the urn, the urn with this Wahlperiode's cards,
 * "Dein Ergebnis", the outcome, sharing and the links back. Once the card is
 * in, it is gone, and the urn opens the screen with the card count and the
 * countdown under it.
 */
function Result({
  number,
  playDate,
  puzzle,
  schedule,
  stamping,
  onReview,
  onOpenDay,
  canOpenDay,
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
    // Each block of the screen gets room of its own; inside a block, its
    // parts stay close.
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
              // Ripples out from the card while it waits to be cast.
              <span
                aria-hidden
                className="pointer-events-none absolute inset-0 animate-stimmts-pulse rounded-[10px] border-2 border-foreground motion-reduce:hidden"
              />
            )}
            <Stimmkarte
              ref={cardRef}
              number={number}
              playDate={playDate}
              title={puzzle.title}
              topic={puzzle.topic}
              score={score.correct}
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
        <div className="flex flex-col items-center gap-4">
          {/* Once the card, which carries it, is in the urn. */}
          <StimmtsLogo className="text-[26px]" />
          <Countdown />
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
              'text-center text-sm text-muted-foreground',
              justCast &&
                'animate-stimmts-screen [animation-delay:0.5s] motion-reduce:animate-none',
            )}
          >
            <span className="font-display text-2xl font-extrabold tabular-nums text-foreground">
              {cards}/{PERIOD_LENGTH}
            </span>{' '}
            Stimmkarten abgegeben
          </p>
        )}
      </div>

      <section aria-live="polite" className="flex flex-col gap-5">
        <div className="flex flex-col items-center gap-1">
          <span className="text-sm text-muted-foreground">Dein Ergebnis</span>
          <p className="font-display text-5xl font-extrabold tabular-nums leading-[52px] tracking-[-0.02em]">
            {score.correct} von {score.total}
            <small className="ml-2 font-sans text-lg font-semibold leading-none tracking-normal text-muted-foreground">
              richtig
            </small>
          </p>
        </div>
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
              <Verdict correct={entry.correct} />
              <span className="sr-only">{partyLabel(entry.partyId)}</span>
            </li>
          ))}
        </ul>
      </section>

      <OutcomeCard puzzle={puzzle} onOpen={onReview} />

      <div className="relative px-6">
        <PeriodChamber
          seats={periodSeats(period.days, false)}
          complete={period.complete}
          today={number}
          onOpen={onOpenDay}
          canOpen={canOpenDay}
          className="mx-auto max-w-[300px]"
        />
        <div className="absolute bottom-0 left-1/2 flex -translate-x-1/2 flex-col items-center whitespace-nowrap">
          <span className="font-display text-[30px] font-extrabold tabular-nums leading-[34px] tracking-[-0.02em]">
            Tag {period.day}
          </span>
          <span className="text-xs font-medium text-muted-foreground">
            von {PERIOD_LENGTH}
          </span>
        </div>
      </div>

      <ShareButton
        text={buildShareText({
          puzzleNumber: number,
          score,
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
      />
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
      <span className="relative flex items-center gap-2.5 rounded-full bg-foreground py-2.5 pl-3 pr-5 font-display text-[17px] font-bold text-background shadow-lg">
        {/* The bubble's tail, pointing up at the card. */}
        <span className="absolute -top-1.5 left-1/2 size-3 -translate-x-1/2 rotate-45 rounded-[2px] bg-foreground" />
        <span className="flex size-8 items-center justify-center rounded-full bg-background/15">
          <Pointer
            strokeWidth={2.25}
            className="size-5 animate-stimmts-tap motion-reduce:animate-none"
          />
        </span>
        Tippe auf deine Stimmkarte
      </span>
    </p>
  );
}

export default Result;
