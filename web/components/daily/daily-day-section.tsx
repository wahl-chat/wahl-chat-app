'use client';

import type { RankedDay } from '@/lib/daily/feed';
import { type DetailItem, protocolLabel } from '@/lib/daily/items';
import type { DailyDigest } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { META_TEXT } from './card-styles';
import { useSnapCarousel } from './carousel';
import { PlenaryCard } from './plenary-card';
import VoteCard from './vote-card';

const dayFormat = new Intl.DateTimeFormat('de-DE', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  timeZone: 'UTC',
});

const shortDayFormat = new Intl.DateTimeFormat('de-DE', {
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
});

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
  const protocol = protocolLabel(digest);
  const meta = [
    kind === 'sitting' ? 'Plenarsitzung' : 'Abstimmung',
    digest.parliament !== 'bundestag' && digest.parliament_name,
    protocol && `Protokoll ${protocol}`,
  ]
    .filter(Boolean)
    .join(' · ');
  return (
    <header className="flex items-start justify-between gap-3">
      <div>
        <p className={META_TEXT}>{meta}</p>
        <h3 className="text-[19px] font-bold">
          {dayFormat.format(utcDay(digest.date))}
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
  const { ref, active, onScroll } = useSnapCarousel(12);
  return (
    <div className="flex flex-col gap-3">
      <GroupHeader
        kind="sitting"
        digest={digest}
        count={items.length > 1 ? `${active + 1} / ${items.length}` : undefined}
      />
      <div
        ref={ref}
        onScroll={onScroll}
        className="relative -mx-4 flex snap-x snap-mandatory scroll-px-4 gap-3 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
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
      </div>
    </div>
  );
}

type Props = {
  day: RankedDay;
  onOpen: (item: DetailItem) => void;
};

/**
 * One sitting day, ranked within itself: the day's most heated debate, a vote
 * on the same topic, then the rest per parliament.
 */
function DailyDaySection({ day, onOpen }: Props) {
  const { hot, match } = day;
  return (
    <section
      className="flex flex-col gap-8"
      aria-label={dayFormat.format(utcDay(day.date))}
    >
      {hot && (
        <div className="flex flex-col gap-3">
          <header className="flex items-baseline justify-between gap-3">
            <h2 className="text-lg font-bold">Thema des Tages</h2>
            <span className={META_TEXT}>
              {hot.digest.parliament === 'bundestag'
                ? 'Plenarsitzung'
                : hot.digest.parliament_name}{' '}
              · {shortDayFormat.format(utcDay(day.date))}
            </span>
          </header>
          <PlenaryCard
            item={hot}
            heat={day.heat.get(hot.key)}
            onOpen={() => onOpen(hot)}
            variant="hot"
          />
          {match && (
            <div className="flex flex-col gap-2 pt-3">
              <h3 className={META_TEXT}>
                Passende Abstimmung ·{' '}
                {shortDayFormat.format(utcDay(match.digest.date))}
              </h3>
              <VoteCard item={match} onOpen={() => onOpen(match)} compact />
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
