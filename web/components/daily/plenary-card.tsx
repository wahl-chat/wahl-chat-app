import {
  type SectionItem,
  itemTeaser,
  protocolLabel,
  sectionTopics,
} from '@/lib/daily/items';
import { cn } from '@/lib/utils';
import { CardFooter, ItemTeaser } from './card-footer';
import { CARD_SURFACE } from './card-styles';
import { useFeedLocale } from './feed-locale';
import { SectionMediaFrame, sectionMedia } from './speech-videos';
import { TopicMeta } from './topic-chip';

const HEAT_DOTS = 5;

export function HeatDots({ heat }: { heat: number }) {
  const { t } = useFeedLocale();
  return (
    <span
      role="img"
      aria-label={t.heatOutOf(heat, HEAT_DOTS)}
      className="inline-flex gap-0.5"
    >
      {Array.from({ length: HEAT_DOTS }, (_, i) => (
        <span
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length scale
          key={i}
          className={cn(
            'size-1.5 rounded-full',
            i < heat ? 'bg-[#E53935]' : 'bg-[var(--daily-border)]',
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
 * One debate of a Plenarsitzung. The hot variant leads the day, the small one
 * sits in the day's swipe row; both are the same card at different sizes.
 */
export function PlenaryCard({ item, heat, onOpen, variant }: Props) {
  const { t } = useFeedLocale();
  const { section, digest } = item;
  const media = sectionMedia(section, t);
  const hot = variant === 'hot';
  const protocol = protocolLabel(digest);

  return (
    <article
      data-item-key={item.key}
      className={cn(CARD_SURFACE, 'flex h-full flex-col overflow-hidden')}
    >
      {media && <SectionMediaFrame media={media} small={!hot} />}
      <div className="flex flex-1 flex-col gap-2 px-4 pb-2 pt-4">
        <TopicMeta
          topics={sectionTopics(section)}
          suffix={hot && protocol ? t.protocol(protocol) : null}
          trailing={hot && heat ? <HeatDots heat={heat} /> : null}
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
    </article>
  );
}
