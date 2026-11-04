import {
  type SectionItem,
  itemTeaser,
  protocolLabel,
  sectionTopics,
} from '@/lib/daily/items';
import { cn } from '@/lib/utils';
import { FlameIcon } from 'lucide-react';
import { CardFooter, ItemTeaser } from './card-footer';
import { CARD_SURFACE } from './card-styles';
import HotTopicTrail from './hot-topic-trail';
import { SectionMediaFrame, sectionMedia } from './speech-videos';
import { TopicMeta } from './topic-chip';

const HEAT_SCALE = 5;

/** Heat as a row of small flames, lit up to the debate's rating. */
export function HeatFlames({ heat }: { heat: number }) {
  return (
    <span
      role="img"
      aria-label={`Hitzigkeit ${heat} von ${HEAT_SCALE}`}
      className="inline-flex gap-px"
    >
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

type Props = {
  item: SectionItem;
  /** Day-relative, see `dayHeat`. */
  heat: number | undefined;
  onOpen: () => void;
  variant: 'hot' | 'small';
};

/**
 * One debate of a Plenarsitzung. The hot variant leads the day as its Hot
 * Topic, the small one sits in the day's swipe row; both are the same card at
 * different sizes, and both show the heat, since it helps choose what to read.
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
        'flex h-full flex-col overflow-hidden',
        hot && 'relative',
      )}
    >
      {media && <SectionMediaFrame media={media} small={!hot} />}
      <div className="flex flex-1 flex-col gap-2 px-4 pb-2 pt-4">
        <TopicMeta
          topics={sectionTopics(section)}
          suffix={hot && protocol ? `Protokoll ${protocol}` : null}
          trailing={heat ? <HeatFlames heat={heat} /> : null}
        />
        <h3
          className={cn(
            'hyphens-auto break-words font-bold leading-snug',
            hot ? 'text-[22px]' : 'text-[19px]',
          )}
        >
          <button
            type="button"
            onClick={onOpen}
            className="text-left focus-visible:underline focus-visible:outline-none"
          >
            {section.headline}
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
