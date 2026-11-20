import {
  ABOVE_CARD_LINK,
  CARD_GROUP,
  CARD_LINK,
  CARD_SURFACE,
  HEADLINE_POP,
  HEMICYCLE_POP,
  META_TEXT,
} from '@/components/daily/card-styles';
import { OutcomeBadge } from '@/components/daily/outcome-badge';
import { TopicDot } from '@/components/daily/topic-chip';
import { chamberCenter, chamberStates } from '@/lib/stimmts/game-view';
import {
  type VoteTotals,
  voteCountLabels,
  voteTotals,
} from '@/lib/stimmts/score';
import { isAbgeordnetenwatch } from '@/lib/stimmts/source';
import { feedTopicFor } from '@/lib/stimmts/topic';
import type { Puzzle, PuzzleOutcome } from '@/lib/stimmts/types';
import { cn } from '@/lib/utils';
import { ArrowUpRight } from 'lucide-react';
import Image from 'next/image';
import { useId } from 'react';
import Hemicycle from './hemicycle';
import VoteDot, { type DotKind } from './vote-dot';

// The feed's badge speaks the feed's outcome words.
const FEED_OUTCOME = {
  accepted: 'angenommen',
  rejected: 'abgelehnt',
} as const satisfies Record<PuzzleOutcome, string>;

const DOT_KIND: Record<keyof VoteTotals, DotKind> = {
  yes: 'yes',
  no: 'no',
  abstain: 'abstain',
  noShow: 'absent',
};

/**
 * How the Bundestag actually voted, as the feed shows a vote: topic, outcome,
 * title, the chamber and its counts, and the source. The game's own chamber
 * draws it rather than the feed's, since the feed's needs each party's name
 * and colour as data and the game keeps those in its theme. The whole card
 * opens the vote with every member's seat; the source link sits above that.
 */
function VoteResultCard({
  puzzle,
  onOpen,
}: {
  puzzle: Puzzle;
  onOpen: () => void;
}) {
  const all = new Set(puzzle.parties.map((party) => party.partyId));
  const counts = voteCountLabels(voteTotals(puzzle));
  const headingId = useId();

  return (
    <article
      aria-labelledby={headingId}
      className={cn(
        CARD_SURFACE,
        CARD_GROUP,
        'flex flex-col gap-2.5 px-4 pt-4',
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <p className={cn(META_TEXT, 'flex min-w-0 items-center gap-1.5')}>
          <TopicDot topic={feedTopicFor(puzzle.topic) ?? 'other'} />
          <span className="min-w-0 truncate">
            {`${puzzle.topic} · Namentliche Abstimmung`}
          </span>
        </p>
        <OutcomeBadge
          outcome={FEED_OUTCOME[puzzle.outcome]}
          className="px-2.5 py-0.5 text-xs"
        />
      </div>
      <h2
        id={headingId}
        className="hyphens-auto break-words text-[19px] font-bold leading-snug"
      >
        <button type="button" onClick={onOpen} className={CARD_LINK}>
          <span className={HEADLINE_POP}>{puzzle.title}</span>
        </button>
      </h2>
      {/* Clicks pass through to the card's link, which opens the vote. */}
      <div className={cn('pointer-events-none -mx-1', HEMICYCLE_POP)}>
        <Hemicycle
          parties={puzzle.parties}
          unaffiliated={puzzle.unaffiliated}
          states={chamberStates(puzzle, 'result', {}, all)}
          center={chamberCenter(puzzle, 'result', {}, all)}
        />
      </div>
      <ul
        aria-label="Stimmen"
        className="flex flex-wrap justify-center gap-x-3 gap-y-1 text-[13px] tabular-nums"
      >
        {counts.map(({ vote, label }) => (
          <li key={vote} className="inline-flex items-center gap-1.5">
            <VoteDot kind={DOT_KIND[vote]} className="size-[9px]" />
            {label}
          </li>
        ))}
      </ul>
      <a
        href={puzzle.source.url}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          ABOVE_CARD_LINK,
          META_TEXT,
          '-mx-4 mt-0.5 flex min-h-10 items-center justify-between gap-3 rounded-b-xl border-t border-[var(--daily-border)] px-4 transition-colors hover:text-[var(--daily-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--daily-ink)]',
        )}
      >
        {isAbgeordnetenwatch(puzzle.source.url) ? (
          <span className="flex items-center gap-2">
            Quelle
            <AbgeordnetenwatchLogo />
          </span>
        ) : (
          `Quelle: ${puzzle.source.label}`
        )}
        <ArrowUpRight aria-hidden className="size-3.5 flex-none" />
      </a>
    </article>
  );
}

/**
 * Abgeordnetenwatch's logo from its press kit. Its letters are cut out, so the
 * purple version reads on a light card and the white one on a dark one. Which
 * card is dark is the style's call, not the site's, so the switch lives in
 * CSS (`.stimmts-aw-*`), which follows the frame's `data-stimmts-mode`.
 */
function AbgeordnetenwatchLogo() {
  return (
    <>
      <Image
        alt="Abgeordnetenwatch"
        width={56}
        height={32}
        src="/images/stimmts/abgeordnetenwatch.png"
        className="stimmts-aw-light h-6 w-auto"
      />
      <Image
        alt="Abgeordnetenwatch"
        width={56}
        height={32}
        src="/images/stimmts/abgeordnetenwatch-dark.png"
        className="stimmts-aw-dark h-6 w-auto"
      />
    </>
  );
}

export default VoteResultCard;
