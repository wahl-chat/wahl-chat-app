'use client';

import type { FeedPick } from '@/lib/chat-feed';
import { layoutHemicycle } from '@/lib/daily/hemicycle';
import { SEAT_FILLS } from '@/lib/daily/palette';
import { cn } from '@/lib/utils';
import { PlayIcon, VoteIcon } from 'lucide-react';
import { useMemo, useState } from 'react';

type Props = {
  pick: FeedPick;
  className?: string;
};

/** A feed item at a glance, as in the feed: a vote's hemicycle, a debate's
 * video frame. Decorative; the headline next to it carries the meaning. */
function FeedPickThumb({ pick, className }: Props) {
  return (
    <span
      aria-hidden
      className={cn(
        'relative flex aspect-video shrink-0 items-center justify-center overflow-hidden rounded-md',
        pick.kind === 'vote' ? 'bg-muted' : 'bg-zinc-800',
        className,
      )}
    >
      {pick.kind === 'vote' ? (
        <VoteThumb pick={pick} />
      ) : (
        <VideoThumb pick={pick} />
      )}
    </span>
  );
}

function VoteThumb({ pick }: { pick: FeedPick }) {
  const layout = useMemo(() => layoutHemicycle(pick.parties), [pick.parties]);
  if (layout.seats.length === 0) {
    return <VoteIcon className="size-5 text-muted-foreground" />;
  }
  const r = layout.seatRadius;
  return (
    <svg viewBox="-1.08 -1.08 2.16 1.16" className="w-[86%]">
      {layout.seats.map((seat, i) => (
        <circle
          // biome-ignore lint/suspicious/noArrayIndexKey: stable per layout
          key={i}
          cx={seat.x.toFixed(4)}
          cy={(-seat.y).toFixed(4)}
          r={r.toFixed(4)}
          fill={
            seat.vote === 'absent'
              ? '#D4D4D8'
              : SEAT_FILLS[seat.vote as keyof typeof SEAT_FILLS]
          }
        />
      ))}
    </svg>
  );
}

function VideoThumb({ pick }: { pick: FeedPick }) {
  const [broken, setBroken] = useState(false);
  return (
    <>
      {pick.poster && !broken && (
        <img
          src={pick.poster}
          alt=""
          loading="lazy"
          onError={() => setBroken(true)}
          className="absolute inset-0 size-full object-cover"
        />
      )}
      <span className="relative flex size-7 items-center justify-center rounded-full bg-black/60 text-white">
        <PlayIcon className="ml-0.5 size-3.5 fill-current" />
      </span>
      {pick.minutes != null && (
        <span className="absolute bottom-1 right-1 rounded bg-black/70 px-1 text-[10px] font-medium tabular-nums leading-4 text-white">
          {Math.round(pick.minutes)} Min.
        </span>
      )}
    </>
  );
}

export default FeedPickThumb;
