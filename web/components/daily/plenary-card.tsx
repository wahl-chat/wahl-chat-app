import {
  type SectionItem,
  openingParty,
  protocolLabel,
} from '@/lib/daily/items';
import { cn } from '@/lib/utils';
import { CARD_SURFACE, MUTED_TEXT, SECTION_LABEL } from './card-styles';
import InterestFeedback from './interest-feedback';
import { PartyPositions } from './party-positions';
import { SectionMediaFrame, sectionMedia } from './speech-videos';
import { TopicMeta } from './topic-chip';
import { MoreLink } from './vote-card';

const HEAT_DOTS = 5;

export function formatDuration(minutes: number): string {
  return `ca. ${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')} h`;
}

export function HeatDots({ heat }: { heat: number }) {
  return (
    <span
      role="img"
      aria-label={`Hitzigkeit ${heat} von ${HEAT_DOTS}`}
      className="inline-flex gap-1"
    >
      {Array.from({ length: HEAT_DOTS }, (_, i) => (
        <span
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed-length scale
          key={i}
          className={cn(
            'size-2 rounded-full',
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
 * One debate of a Plenarsitzung. The hot variant leads the day with the
 * opening statement and the first three Fraktionen; the small one sits in the
 * day's swipe row.
 */
export function PlenaryCard({ item, heat, onOpen, variant }: Props) {
  const { section, digest } = item;
  const media = sectionMedia(section);
  const hot = variant === 'hot';
  const protocol = protocolLabel(digest);
  const title = (
    <button
      type="button"
      onClick={onOpen}
      className="text-left focus-visible:underline focus-visible:outline-none"
    >
      {section.headline}
    </button>
  );

  return (
    <article
      data-item-key={item.key}
      className={cn(CARD_SURFACE, 'flex h-full flex-col overflow-hidden')}
    >
      {media && <SectionMediaFrame media={media} small={!hot} />}
      <div className="flex flex-1 flex-col gap-3 p-4">
        <TopicMeta
          topics={[section.topic]}
          suffix={hot && protocol ? `Protokoll ${protocol}` : null}
        />
        <h3
          className={cn(
            'hyphens-auto break-words font-bold leading-snug',
            hot ? 'text-[22px]' : 'text-[19px]',
          )}
        >
          {title}
        </h3>
        {hot && (
          <>
            {(section.debate_minutes || heat) && (
              <p
                className={cn(
                  'flex flex-wrap items-center gap-x-4 text-[15px]',
                  MUTED_TEXT,
                )}
              >
                {section.debate_minutes ? (
                  <span>Dauer {formatDuration(section.debate_minutes)}</span>
                ) : null}
                {heat ? (
                  <span className="flex items-center gap-2">
                    Hitzigkeit <HeatDots heat={heat} />
                  </span>
                ) : null}
              </p>
            )}
            {section.opening_quote && (
              <figure className="rounded-xl bg-[var(--daily-surface)] p-4">
                <figcaption className={cn('text-sm', MUTED_TEXT)}>
                  Ausgangsstatement · {section.opening_quote.speaker} (
                  {section.opening_quote.party_name})
                </figcaption>
                <blockquote className="mt-1 text-[17px] font-medium leading-snug">
                  „{section.opening_quote.text}“
                </blockquote>
              </figure>
            )}
            {section.positions && section.positions.length > 0 && (
              <div>
                <span className={cn(SECTION_LABEL, 'sr-only')}>
                  Wer sagt was
                </span>
                <PartyPositions
                  positions={section.positions}
                  openedBy={openingParty(section)}
                  limit={3}
                  clamp
                />
              </div>
            )}
          </>
        )}
        <div
          className={cn(
            'mt-auto flex items-center gap-2 border-t border-[var(--daily-border)] pt-3',
          )}
        >
          {hot && <MoreLink onOpen={onOpen} label={section.headline} />}
          <InterestFeedback
            itemKey={item.key}
            grouped={hot}
            className="flex-1"
          />
        </div>
      </div>
    </article>
  );
}
