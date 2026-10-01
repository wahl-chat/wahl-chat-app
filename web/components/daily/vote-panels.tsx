'use client';

import { partyColor } from '@/lib/daily/palette';
import { sortBySeating } from '@/lib/daily/seating-order';
import type { DigestVote } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ArrowRightIcon, ExternalLinkIcon } from 'lucide-react';
import { useRef, useState } from 'react';
import { CARD_SURFACE, INK_LABEL, MUTED_TEXT } from './card-styles';
import { SeatLegend } from './hemicycle';
import TopicChip from './topic-chip';
import VoteCard, { VoteTotalsLine } from './vote-card';

const TABLE_RULE =
  'border-[color-mix(in_srgb,var(--daily-ink)_18%,transparent)]';

export function PartyVoteTable({ vote }: { vote: DigestVote }) {
  return (
    <table className="w-full text-sm tabular-nums">
      <thead className="text-[11px] uppercase tracking-[0.12em]">
        <tr className="border-b-2 border-[var(--daily-ink)]">
          <th className="py-1.5 text-left font-bold">Fraktion</th>
          <th className="py-1.5 text-right font-bold">Ja</th>
          <th className="py-1.5 text-right font-bold">Nein</th>
          <th className="py-1.5 text-right font-bold">Enth.</th>
          <th className="py-1.5 text-right font-bold">Abw.</th>
        </tr>
      </thead>
      <tbody>
        {sortBySeating(vote.parties).map((party) => (
          <tr key={party.party_id} className={cn('border-b', TABLE_RULE)}>
            <td className="flex items-center gap-2 py-1.5 font-medium">
              <span
                className="inline-block size-2.5 shrink-0 rounded-[2px] border-[1.5px] border-[var(--daily-ink)]"
                style={{
                  backgroundColor: partyColor(party.party_id, party.color),
                }}
              />
              {party.name}
            </td>
            <td className="py-1.5 text-right">{party.yes}</td>
            <td className="py-1.5 text-right">{party.no}</td>
            <td className="py-1.5 text-right">{party.abstain}</td>
            <td className="py-1.5 text-right">{party.no_show}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function SourceLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs font-bold underline decoration-[1.5px] underline-offset-[3px] hover:decoration-[3px]"
    >
      {children}
      <ExternalLinkIcon className="size-3" />
    </a>
  );
}

function OpenDetailsButton({ onOpen }: { onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="mt-auto flex w-fit items-center gap-1.5 pt-2 text-xs font-bold uppercase tracking-[0.14em] underline decoration-2 underline-offset-4"
    >
      Details & Quellen <ArrowRightIcon className="size-3.5" />
    </button>
  );
}

/** Second carousel card: what the motion is actually about. */
function VoteDetailsPanel({
  vote,
  onOpen,
}: {
  vote: DigestVote;
  onOpen: () => void;
}) {
  return (
    <div className={cn(CARD_SURFACE, 'flex h-full flex-col gap-3 p-5')}>
      <span className={INK_LABEL}>Worum es geht</span>
      <div className="flex flex-wrap gap-1.5">
        {vote.topics.map((topic) => (
          <TopicChip key={topic} topic={topic} />
        ))}
      </div>
      {vote.summary && (
        <p className="font-display text-lg font-bold leading-snug">
          {vote.summary}
        </p>
      )}
      {vote.description && (
        // Clamped to keep the strip compact; the dialog shows the full text.
        <p className="line-clamp-[9] text-sm leading-relaxed">
          {vote.description}
        </p>
      )}
      <p className={cn('text-xs', MUTED_TEXT)}>Originaltitel: {vote.title}</p>
      {vote.citation_url && (
        <SourceLink href={vote.citation_url}>
          Abstimmung auf abgeordnetenwatch.de
        </SourceLink>
      )}
      <OpenDetailsButton onOpen={onOpen} />
    </div>
  );
}

/** Third carousel card: the per-party breakdown, absentees included. */
function VoteTablePanel({
  vote,
  onOpen,
}: {
  vote: DigestVote;
  onOpen: () => void;
}) {
  return (
    <div className={cn(CARD_SURFACE, 'flex h-full flex-col gap-3 p-5')}>
      <span className={INK_LABEL}>So haben die Fraktionen gestimmt</span>
      <PartyVoteTable vote={vote} />
      <VoteTotalsLine vote={vote} />
      <SeatLegend />
      <OpenDetailsButton onOpen={onOpen} />
    </div>
  );
}

const PANEL_LABELS = ['Ergebnis', 'Worum es geht', 'Fraktionen'];

/**
 * On mobile a vote is a swipeable strip of three cards: the result, the
 * substance, the per-party table. From md up only the result card shows; the
 * rest is one click away in the detail dialog.
 */
export function VoteCarousel({
  vote,
  onOpen,
}: {
  vote: DigestVote;
  onOpen: () => void;
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  const onScroll = () => {
    const el = scroller.current;
    const first = el?.firstElementChild as HTMLElement | null;
    if (!el || !first) {
      return;
    }
    // Card width plus the gap between cards.
    const step = first.offsetWidth + 16;
    setActive(Math.round(el.scrollLeft / step));
  };

  const goTo = (index: number) => {
    const card = scroller.current?.children[index] as HTMLElement | undefined;
    card?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'start',
    });
  };

  return (
    <div className="flex flex-col gap-2">
      <div
        ref={scroller}
        onScroll={onScroll}
        // Padding keeps the stamps (above) and the offset shadows (right,
        // bottom) inside the scroll box, which would otherwise clip them.
        className="-mx-4 flex snap-x snap-mandatory scroll-px-4 items-start gap-4 overflow-x-auto px-4 pb-2 pt-4 [scrollbar-width:none] md:mx-0 md:block md:overflow-visible md:p-0 [&::-webkit-scrollbar]:hidden"
      >
        <div className="w-[86%] shrink-0 snap-start md:w-auto">
          <VoteCard vote={vote} onOpen={onOpen} />
        </div>
        <div className="w-[86%] shrink-0 snap-start md:hidden">
          <VoteDetailsPanel vote={vote} onOpen={onOpen} />
        </div>
        <div className="w-[86%] shrink-0 snap-start md:hidden">
          <VoteTablePanel vote={vote} onOpen={onOpen} />
        </div>
      </div>
      <div className="flex items-center justify-center gap-2 md:hidden">
        {PANEL_LABELS.map((label, i) => (
          <button
            key={label}
            type="button"
            aria-label={`${label} anzeigen`}
            aria-current={active === i}
            onClick={() => goTo(i)}
            className={cn(
              'h-2.5 rounded-full border-2 border-[var(--daily-ink)] transition-[width] motion-reduce:transition-none',
              active === i ? 'w-6 bg-[var(--daily-ink)]' : 'w-2.5',
            )}
          />
        ))}
      </div>
    </div>
  );
}
