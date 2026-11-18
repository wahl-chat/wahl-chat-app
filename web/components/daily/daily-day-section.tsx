'use client';

import { LOCALE_INFO } from '@/i18n/locales';
import type { RankedDay } from '@/lib/daily/feed';
import { type DetailItem, protocolLabel } from '@/lib/daily/items';
import type { DailyDigest } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { useLocale, useTranslations } from 'next-intl';
import { META_TEXT } from './card-styles';
import { useSnapCarousel } from './carousel';
import { HeatInfo, PlenaryCard } from './plenary-card';
import { ScrollRow, slideStep } from './scroll-row';
import VoteCard from './vote-card';

function dayFormat(intl: string) {
  return new Intl.DateTimeFormat(intl, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    timeZone: 'UTC',
  });
}

// The carousel's gap-3.
const SLIDE_GAP_PX = 12;

function shortDayFormat(intl: string) {
  return new Intl.DateTimeFormat(intl, {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  });
}

function utcDay(isoDay: string): Date {
  return new Date(`${isoDay}T00:00:00Z`);
}

/** "Plenarsitzung · Protokoll 21/91" over "Dienstag, 8. September". */
function GroupHeader({
  kind,
  digest,
  count,
}: {
  kind: 'sitting' | 'vote';
  digest: DailyDigest;
  count?: string;
}) {
  const t = useTranslations('feed');
  const intl = LOCALE_INFO[useLocale()].intl;
  const protocol = protocolLabel(digest);
  const meta = [
    kind === 'sitting' ? t('plenarySitting') : t('vote'),
    digest.parliament !== 'bundestag' && digest.parliament_name,
    protocol && t('protocol', { id: protocol }),
  ]
    .filter(Boolean)
    .join(' · ');
  return (
    <header className="flex items-start justify-between gap-3">
      <div>
        <p className={META_TEXT}>{meta}</p>
        <h3 className="text-[19px] font-bold">
          {dayFormat(intl).format(utcDay(digest.date))}
        </h3>
      </div>
      {count && <span className={cn(META_TEXT, 'tabular-nums')}>{count}</span>}
    </header>
  );
}

/** The day's other debates as a swipe row, counted "1 / n" as it scrolls. */
function PlenaryRow({
  digest,
  items,
  heat,
  onOpen,
}: {
  digest: DailyDigest;
  items: RankedDay['blocks'][number]['sections'];
  heat: Map<string, number>;
  onOpen: (item: DetailItem) => void;
}) {
  const t = useTranslations('feed');
  const { ref, active, onScroll } = useSnapCarousel(SLIDE_GAP_PX);
  return (
    <div className="flex flex-col gap-3">
      <GroupHeader
        kind="sitting"
        digest={digest}
        count={items.length > 1 ? `${active + 1} / ${items.length}` : undefined}
      />
      <ScrollRow
        label={t('debates')}
        scrollerRef={ref}
        onScroll={onScroll}
        step={slideStep(SLIDE_GAP_PX)}
        className="snap-x snap-mandatory scroll-px-4 gap-3"
      >
        {items.map((item) => (
          <div
            key={item.key}
            className={cn(
              'shrink-0 snap-start',
              items.length > 1 ? 'w-[86%] md:w-[48%]' : 'w-full',
            )}
          >
            <PlenaryCard
              item={item}
              heat={heat.get(item.key)}
              onOpen={() => onOpen(item)}
              variant="small"
            />
          </div>
        ))}
      </ScrollRow>
    </div>
  );
}

type Props = {
  day: RankedDay;
  onOpen: (item: DetailItem) => void;
};

/**
 * One sitting day, ranked within itself: the Hot Topic (the day's most heated
 * debate), the vote on it if there was one that day, then the rest per
 * parliament.
 */
function DailyDaySection({ day, onOpen }: Props) {
  const t = useTranslations('feed');
  const intl = LOCALE_INFO[useLocale()].intl;
  const { hot, match } = day;
  return (
    <section
      id={`tag-${day.date}`}
      // Focusable from script only, for a jump from the sitting calendar. The
      // jump stops below the header and the sticky filter bar (4.5rem).
      tabIndex={-1}
      className="flex scroll-mt-[calc(var(--header-height,4rem)+4.5rem+1rem)] flex-col gap-8"
      aria-label={dayFormat(intl).format(utcDay(day.date))}
    >
      {hot && (
        <div className="flex flex-col gap-3">
          <header className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold">{t('hotTopic')}</h2>
              {day.heat.has(hot.key) && (
                <HeatInfo heat={day.heat.get(hot.key) as number} />
              )}
            </div>
            <span className={META_TEXT}>
              {hot.digest.parliament === 'bundestag'
                ? t('plenarySitting')
                : hot.digest.parliament_name}{' '}
              · {shortDayFormat(intl).format(utcDay(day.date))}
            </span>
          </header>
          {/* Its flames sit next to "Hot Topic" above, not on the card. */}
          <PlenaryCard item={hot} onOpen={() => onOpen(hot)} variant="hot" />
          {match && (
            <div className="flex flex-col gap-2 pt-3">
              <h3 className={META_TEXT}>{t('voteOnDebate')}</h3>
              <VoteCard item={match} onOpen={() => onOpen(match)} hot />
            </div>
          )}
        </div>
      )}

      {day.blocks.map(({ digest, sections, votes }) => (
        <div key={digest.id} className="flex flex-col gap-8">
          {sections.length > 0 && (
            <PlenaryRow
              digest={digest}
              items={sections}
              heat={day.heat}
              onOpen={onOpen}
            />
          )}
          {votes.length > 0 && (
            <div className="flex flex-col gap-3">
              <GroupHeader kind="vote" digest={digest} />
              {votes.map((vote) => (
                <VoteCard
                  key={vote.key}
                  item={vote}
                  onOpen={() => onOpen(vote)}
                />
              ))}
            </div>
          )}
        </div>
      ))}
    </section>
  );
}

export default DailyDaySection;
