import { Button } from '@/components/ui/button';
import { BASE_URL } from '@/lib/seo';
import { PUZZLES, SCHEDULE } from '@/lib/stimmts/content';
import { partyLabel } from '@/lib/stimmts/labels';
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
import type { Puzzle } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { cn } from '@/lib/utils';
import { useReducedMotion } from 'motion/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import Countdown from './countdown';
import OutcomeLine from './outcome-line';
import PartyTile from './party-tile';
import ShareButton from './share-button';
import Stimmkarte from './stimmkarte';
import Urn from './urn';
import { Verdict } from './vote-pill';

/** How long the Stimmkarte takes to fly into the urn (see stimmts-cast). */
const CAST_MS = 820;

type Props = {
  number: number;
  playDate: string;
  puzzle: Puzzle;
  /** Stamp the score on with a little bounce (the first time only). */
  stamping: boolean;
  onReview: () => void;
};

/**
 * The end of the day's puzzle, top to bottom: the stamped Stimmkarte, which
 * the player casts into the urn, the urn with this Wahlperiode's cards,
 * "Dein Ergebnis", the outcome, sharing and the links back. Once the card is
 * in, it is gone, and the urn opens the screen with the card count and the
 * countdown under it.
 */
function Result({ number, playDate, puzzle, stamping, onReview }: Props) {
  const progress = useProgress((state) => state.progress);
  const castCard = useProgress((state) => state.cast);
  const reduceMotion = useReducedMotion() ?? false;
  // Read once, so a later render cannot cut the stamp's bounce short.
  const [stampOnMount] = useState(stamping);
  const game = getGame(progress, puzzle.id);
  const score = scorePuzzle(puzzle, game.guesses);

  const { cards, sharedPeriod } = useMemo(() => {
    const records = dayRecords({
      schedule: SCHEDULE,
      puzzles: PUZZLES,
      progress,
      throughNumber: number,
    });
    const { days } = currentWahlperiode(records, number, game.cast);
    return {
      cards: days.filter((day) => day.kind === 'played').length,
      // The image shows today in its seat whether or not the card is cast.
      sharedPeriod: encodePeriod(
        currentWahlperiode(records, number, true).days,
      ),
    };
  }, [progress, number, game.cast]);

  const cardRef = useRef<HTMLElement>(null);
  const slotRef = useRef<SVGPolygonElement>(null);
  const [casting, setCasting] = useState(false);
  const [justCast, setJustCast] = useState(false);
  const castTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(castTimer.current), []);

  const finishCast = () => {
    castCard(puzzle.id);
    setJustCast(true);
  };
  const cast = () => {
    const card = cardRef.current;
    const slot = slotRef.current;
    if (casting) {
      return;
    }
    if (reduceMotion || !card || !slot) {
      finishCast();
      return;
    }
    // The drop is measured, so the card lands wherever the layout puts the urn.
    const from = card.getBoundingClientRect();
    const to = slot.getBoundingClientRect();
    const drop = to.top + to.height / 2 - (from.top + from.height / 2);
    card.style.setProperty('--drop', `${Math.round(drop)}px`);
    setCasting(true);
    castTimer.current = setTimeout(finishCast, CAST_MS);
  };

  return (
    <div className="flex flex-col gap-4">
      {!game.cast && (
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
            casting
              ? 'pointer-events-none z-[5] animate-stimmts-cast'
              : 'origin-bottom animate-stimmts-nudge motion-reduce:animate-none',
          )}
        />
      )}

      <div className="relative">
        {!game.cast && !casting && (
          // Shown for a moment, then gone: the nudging card keeps asking.
          <p className="pointer-events-none absolute inset-x-0 -top-1 z-10 flex animate-stimmts-hint justify-center">
            <span className="rounded-full bg-foreground px-3 py-1.5 text-sm font-medium text-background shadow-sm">
              Tippe auf deine Stimmkarte
            </span>
          </p>
        )}
        <Urn cards={cards} freshCard={justCast} slotRef={slotRef} />
      </div>

      {game.cast && (
        <div className="flex flex-col items-center">
          <p
            className={cn(
              'font-display text-5xl font-extrabold leading-[52px] tracking-[-0.02em] tabular-nums',
              justCast &&
                'animate-stimmts-screen [animation-delay:0.5s] motion-reduce:animate-none',
            )}
          >
            <span aria-hidden>
              {cards}/{PERIOD_LENGTH}
            </span>
            <span className="sr-only">
              {cards} von {PERIOD_LENGTH} Stimmkarten dieser Wahlperiode in der
              Urne
            </span>
          </p>
          <Countdown />
        </div>
      )}

      <section aria-live="polite" className="flex flex-col gap-4">
        <div className="flex flex-col items-center">
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
              <Verdict correct={entry.correct} compact />
              <span className="sr-only">{partyLabel(entry.partyId)}</span>
            </li>
          ))}
        </ul>
        <OutcomeLine puzzle={puzzle} />
      </section>

      <ShareButton
        text={buildShareText({
          puzzleNumber: number,
          score,
          url: `${BASE_URL}${sharedResultPath(number, score.correct)}`,
        })}
        imagePath={shareImagePath({
          format: 'square',
          number,
          score: score.correct,
          period: sharedPeriod,
        })}
        imageName={`stimmts-${number}.png`}
      />
      <p className="text-center text-sm">
        <Button
          variant="link"
          onClick={onReview}
          className="h-auto p-0 text-foreground underline underline-offset-[3px]"
        >
          Abstimmung ansehen
        </Button>
        {' · '}
        <a
          className="underline underline-offset-[3px]"
          href={puzzle.source.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Quelle: {puzzle.source.label}
        </a>
      </p>
    </div>
  );
}

export default Result;
