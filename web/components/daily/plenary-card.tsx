'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { HEAT_SCALE, heatExplanation } from '@/lib/daily/feed';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import {
  type SectionItem,
  itemTeaser,
  protocolLabel,
  sectionTopics,
} from '@/lib/daily/items';
import { cn } from '@/lib/utils';
import { FlameIcon } from 'lucide-react';
import { useState } from 'react';
import { CardFooter, ItemTeaser } from './card-footer';
import {
  ABOVE_CARD_LINK,
  CARD_GROUP,
  CARD_LINK,
  CARD_SURFACE,
  FOCUS_RING,
  HEADLINE_POP,
  MEDIA_POP,
} from './card-styles';
import HotTopicTrail from './hot-topic-trail';
import { SectionMediaFrame, sectionMedia } from './speech-videos';
import { TopicMeta } from './topic-chip';

/** Heat as a row of small flames, lit up to the debate's rating. */
function HeatFlames({ heat }: { heat: number }) {
  return (
    <span aria-hidden className="inline-flex gap-px">
      {Array.from({ length: HEAT_SCALE }, (_, i) => (
        <FlameIcon
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length scale
          key={i}
          aria-hidden
          strokeWidth={1.5}
          className={cn(
            'size-3 fill-current',
            i < heat ? 'text-[#E53935]' : 'text-[var(--daily-border)]',
          )}
        />
      ))}
    </span>
  );
}

/**
 * The flames with what they mean: on hover with a mouse, on tap on a touch
 * screen, where a tooltip would otherwise never open. Inside a card it sits
 * above the card's link, so a tap explains rather than opens the debate.
 */
export function HeatInfo({ heat }: { heat: number }) {
  const [open, setOpen] = useState(false);
  const [counted, rating] = heatExplanation(heat);
  return (
    <Tooltip open={open} onOpenChange={setOpen} delayDuration={150}>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={`Hitzigkeit ${heat} von ${HEAT_SCALE}`}
          onClick={() => setOpen(true)}
          className={cn(
            ABOVE_CARD_LINK,
            FOCUS_RING,
            'inline-flex items-center rounded p-0.5',
          )}
        >
          <HeatFlames heat={heat} />
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="bottom"
        className={cn(
          DAILY_THEME_CLASSES,
          'max-w-64 border-[var(--daily-border)] bg-[var(--daily-canvas)] text-[13px] leading-snug text-[var(--daily-ink)]',
        )}
      >
        <p>{counted}</p>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-1.5 font-semibold">
          <HeatFlames heat={heat} />
          <span>{rating}</span>
        </p>
      </TooltipContent>
    </Tooltip>
  );
}

type Props = {
  item: SectionItem;
  /** Day-relative, see `dayHeat`. The Hot Topic shows its own next to its
   * heading instead. */
  heat?: number;
  onOpen: () => void;
  variant: 'hot' | 'small';
};

/**
 * One debate of a Plenarsitzung. The hot variant leads the day as its Hot
 * Topic, the small one sits in the day's swipe row; both are the same card at
 * different sizes. The small one shows its heat, since it helps choose what to
 * read; the Hot Topic's stands next to its heading.
 */
export function PlenaryCard({ item, heat, onOpen, variant }: Props) {
  const { section, digest } = item;
  const media = sectionMedia(section);
  const hot = variant === 'hot';
  const protocol = protocolLabel(digest);

  return (
    <article
      data-item-key={item.key}
      className={cn(
        CARD_SURFACE,
        CARD_GROUP,
        'flex h-full flex-col overflow-hidden',
      )}
    >
      {media && (
        <SectionMediaFrame
          media={media}
          small={!hot}
          mediaClassName={MEDIA_POP}
        />
      )}
      <div className="flex flex-1 flex-col gap-2 px-4 pb-2 pt-4">
        <TopicMeta
          topics={sectionTopics(section)}
          suffix={hot && protocol ? `Protokoll ${protocol}` : null}
          trailing={heat ? <HeatInfo heat={heat} /> : null}
        />
        <h3
          className={cn(
            'hyphens-auto break-words font-bold leading-snug',
            hot ? 'text-[22px]' : 'text-[19px]',
          )}
        >
          <button type="button" onClick={onOpen} className={CARD_LINK}>
            <span className={HEADLINE_POP}>{section.headline}</span>
          </button>
        </h3>
        <ItemTeaser
          text={itemTeaser(item)}
          label={section.headline}
          onOpen={onOpen}
        />
        <CardFooter item={item} />
      </div>
      {hot && <HotTopicTrail />}
    </article>
  );
}
