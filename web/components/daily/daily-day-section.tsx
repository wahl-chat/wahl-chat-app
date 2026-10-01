import { type FeedDay, formatFeedDay } from '@/lib/daily/feed';
import { cn } from '@/lib/utils';
import { CARD_PLACEHOLDER, INK_LABEL, MUTED_TEXT } from './card-styles';
import type { DetailItem, DigestView } from './detail-items';
import {
  LegislationTeaser,
  PlenaryCard,
  PlenaryPlaceholder,
} from './plenary-card';
import { VoteCarousel } from './vote-panels';

type Props = {
  day: FeedDay;
  views: DigestView[];
  items: DetailItem[];
  selectedTopics: string[];
  onOpen: (index: number) => void;
};

function DailyDaySection({ day, views, items, selectedTopics, onOpen }: Props) {
  const open = (key: string) => onOpen(items.findIndex((i) => i.key === key));
  const shown = views.filter((v) => v.visible);
  const hiddenCount = views.reduce((sum, v) => sum + v.hiddenCount, 0);
  // "Freitag, 10. Juli 2026" → weekday label + big calendar date.
  const [weekday, calendarDay] = formatFeedDay(day.date).split(', ');

  return (
    <section
      className="flex flex-col gap-6"
      aria-labelledby={`day-${day.date}`}
    >
      <h2
        id={`day-${day.date}`}
        className="sticky top-[var(--header-height)] z-10 -mx-1 flex items-end gap-3 border-b-[3px] border-[var(--daily-ink)] bg-[var(--daily-canvas)] px-1 pb-2 pt-4"
      >
        <span className={cn(INK_LABEL, 'mb-1.5')}>{weekday}</span>
        <span className="font-display text-3xl font-black leading-none md:text-4xl">
          {calendarDay}
        </span>
      </h2>

      {shown.length === 0 && (
        <p className={cn('text-sm', MUTED_TEXT)}>
          Nichts zu deinen Themen an diesem Tag
          {hiddenCount > 0 &&
            ` · ${hiddenCount} ${hiddenCount === 1 ? 'weiteres Thema' : 'weitere Themen'}`}
          .
        </p>
      )}

      {shown.map(({ digest, votes }) => (
        <div key={digest.id} className="flex flex-col gap-3">
          <h3 className={INK_LABEL}>{digest.parliament_name}</h3>
          <div className="grid grid-cols-[minmax(0,1fr)] gap-6 md:grid-cols-2">
            <div className="flex min-w-0 flex-col gap-6">
              {digest.session ? (
                <PlenaryCard
                  session={digest.session}
                  selectedTopics={selectedTopics}
                  onOpen={() => open(`${digest.id}:session`)}
                />
              ) : (
                <PlenaryPlaceholder>
                  {digest.parliament === 'bundestag'
                    ? 'Die Zusammenfassung dieser Sitzung folgt, sobald das Plenarprotokoll vorliegt.'
                    : 'Zusammenfassungen der Plenarprotokolle für diesen Landtag folgen bald.'}
                </PlenaryPlaceholder>
              )}
              <LegislationTeaser />
            </div>
            <div className="flex min-w-0 flex-col gap-6">
              {votes.length > 0 ? (
                votes.map((vote) => (
                  <VoteCarousel
                    key={vote.poll_id}
                    vote={vote}
                    onOpen={() => open(`${digest.id}:${vote.poll_id}`)}
                  />
                ))
              ) : (
                <p className={cn(CARD_PLACEHOLDER, 'p-5 text-sm')}>
                  {digest.votes.length > 0
                    ? 'Keine Abstimmungen zu deinen Themen an diesem Tag.'
                    : 'An diesem Tag gab es keine namentlichen Abstimmungen.'}
                </p>
              )}
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}

export default DailyDaySection;
