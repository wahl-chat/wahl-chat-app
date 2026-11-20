'use client';

import {
  CARD_SURFACE,
  FOCUS_RING,
  META_TEXT,
} from '@/components/daily/card-styles';
import { TopicDot } from '@/components/daily/topic-chip';
import { partyLabel, yesMeaning } from '@/lib/stimmts/labels';
import { briefingFront, startMeta } from '@/lib/stimmts/start-view';
import type { Puzzle } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { cn } from '@/lib/utils';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { type ReactNode, useEffect, useId, useRef, useState } from 'react';
import HowToPlay from './how-to-play';
import KeyPoints from './key-points';
import MoreInfo from './more-info';
import PartyTile from './party-tile';
import StartBar from './start-bar';
import StimmtsLogo from './stimmts-logo';
import { YesKey } from './yes-means';

type Props = {
  number: number;
  puzzle: Puzzle;
  playDate: string;
  /** A one-line notice above the game card, such as a goal for today. */
  banner?: ReactNode;
  onStart: () => void;
};

/**
 * The first screen, game first: what to do and with which five parties,
 * then what the vote is about in three sourced points, with "Los geht's"
 * always in reach. It never hints at the outcome.
 */
function StartScreen({ puzzle, banner, onStart }: Props) {
  // Someone with no game saved at all is new here.
  const newPlayer = useProgress(
    (state) => Object.keys(state.progress.games).length === 0,
  );

  return (
    <div className="flex flex-col gap-2.5 md:gap-3.5">
      {banner}
      <section
        aria-labelledby="stimmts-start-task"
        className={cn(
          CARD_SURFACE,
          'flex flex-col gap-2.5 px-4 py-3 md:gap-3 md:px-5 md:py-[18px]',
        )}
      >
        {/* The task comes first in reading order, so a screen reader opens on
            it; the brand row only sits above it on screen. */}
        <div className="flex flex-col gap-2.5">
          <h1
            id="stimmts-start-task"
            className="text-[19px] font-bold leading-[25px] md:text-xl md:leading-[26px]"
          >
            Rate, wie die 5 Fraktionen abgestimmt haben.
          </h1>
          <ul
            aria-label="Fünf Fraktionen, noch nicht getippt"
            className="grid grid-cols-5 gap-1"
          >
            {puzzle.parties.map(({ partyId }) => (
              <li key={partyId} className="flex flex-col items-center gap-1">
                <PartyTile partyId={partyId} size="responsive" />
                <span className="sr-only">{partyLabel(partyId)}</span>
                <span
                  aria-hidden
                  className="inline-flex h-5 w-[30px] items-center justify-center rounded-full border border-dashed border-[var(--daily-muted)] text-xs font-bold text-[var(--daily-muted)]"
                >
                  ?
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="order-first flex items-center gap-2">
          <StimmtsLogo className="text-[19px]" />
          <span className="inline-flex h-5 flex-none items-center rounded-full bg-[var(--daily-ink)] px-2 text-[11px] font-bold text-[var(--daily-canvas)]">
            Tagesquiz
          </span>
          <HowToPlay autoOpen={newPlayer} />
        </div>
      </section>
      <BriefingCard puzzle={puzzle} />
      <StartBar onStart={onStart} />
    </div>
  );
}

/**
 * Front: the topic, title, what "Ja" means and the key points. "Mehr Info"
 * opens the rest under the points on a phone and turns the card over from md
 * up, where the front and the back each fit the screen.
 */
function BriefingCard({ puzzle }: { puzzle: Puzzle }) {
  const [open, setOpen] = useState(false);
  const moreId = useId();
  const titleId = useId();
  const toggle = useRef<HTMLButtonElement>(null);
  const moreHeading = useRef<HTMLHeadingElement>(null);
  const front = briefingFront(puzzle);
  const meta = startMeta(puzzle);

  // Focus follows the content: into the details when they open, and back to
  // "Mehr Info" when they close (from md up the back's own button is gone
  // then). Not on the first render, where nothing was toggled.
  const toggled = useRef(false);
  useEffect(() => {
    if (!toggled.current) {
      return;
    }
    if (open) {
      moreHeading.current?.focus({ preventScroll: true });
      // On a phone the details open under the key points, mostly below the
      // fold, so they move up under the sticky header: what just opened is
      // what the player wants to read next. From md up the card turns over
      // in place and the page stays put.
      if (!window.matchMedia('(min-width: 768px)').matches) {
        document.getElementById(moreId)?.scrollIntoView({ block: 'start' });
      }
    } else {
      toggle.current?.focus();
    }
  }, [open, moreId]);
  const setOpenFromUser = (next: boolean) => {
    toggled.current = true;
    setOpen(next);
  };

  return (
    <article
      lang="de"
      aria-labelledby={titleId}
      className={cn(
        CARD_SURFACE,
        'flex flex-col gap-2.5 px-4 pb-1.5 pt-3 md:gap-3 md:px-5 md:pb-2 md:pt-[18px]',
      )}
    >
      {/* From md up the open card shows only its back. */}
      <div
        className={cn('flex flex-col gap-2.5 md:gap-3', open && 'md:hidden')}
      >
        <div className="flex flex-col gap-1">
          <p className={cn(META_TEXT, 'flex items-center gap-1.5')}>
            <TopicDot topic={meta.feedTopic} />
            <span>{meta.label}</span>
          </p>
          <h2
            id={titleId}
            className="text-lg font-bold leading-6 md:text-xl md:leading-[26px]"
          >
            {puzzle.title}
          </h2>
        </div>
        <p className="flex items-start gap-2.5 text-sm leading-[21px] md:items-center md:gap-3 md:text-[15px] md:leading-[22px]">
          <YesKey className="h-[26px] gap-1.5 px-2.5 text-sm font-semibold md:h-7 md:gap-2 md:px-3 md:text-[15px]" />
          <span className="mt-0.5 md:mt-0">
            heißt: {yesMeaning(puzzle.yesMeans)}
          </span>
        </p>
        {front.kind === 'points' ? (
          <KeyPoints points={front.points} />
        ) : (
          <p
            lang="de"
            className="hyphens-auto text-[15px] leading-[22px] text-[var(--daily-body)]"
          >
            {front.text}
          </p>
        )}
        <button
          ref={toggle}
          type="button"
          aria-expanded={open}
          aria-controls={moreId}
          onClick={() => setOpenFromUser(!open)}
          className={cn(
            FOCUS_RING,
            'inline-flex min-h-11 items-center gap-1.5 self-start rounded-sm text-[15px] font-semibold text-[var(--daily-ink)] md:min-h-10',
          )}
        >
          {open ? 'Weniger anzeigen' : 'Mehr Info'}
          <ChevronDown
            aria-hidden
            strokeWidth={2.25}
            className={cn(
              'size-4 transition-transform motion-reduce:transition-none md:hidden',
              open && 'rotate-180',
            )}
          />
          <ArrowRight
            aria-hidden
            strokeWidth={2.25}
            className="hidden size-4 md:block"
          />
        </button>
      </div>
      <MoreInfo
        id={moreId}
        puzzle={puzzle}
        briefingOnFront={front.kind === 'briefing'}
        hidden={!open}
        headingRef={moreHeading}
        onClose={() => setOpenFromUser(false)}
      />
    </article>
  );
}

export default StartScreen;
