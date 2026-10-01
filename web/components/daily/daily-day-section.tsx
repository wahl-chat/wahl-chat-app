import { type FeedDay, formatFeedDay } from '@/lib/daily/feed';
import { cn } from '@/lib/utils';
import { CARD_PLACEHOLDER } from './card-styles';
import type { DetailItem, DigestView } from './detail-items';
import {
  LegislationTeaser,
  PlenaryCard,
  PlenaryPlaceholder,
} from './plenary-card';
import VoteCard from './vote-card';

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

  return (
    <section
      className="flex flex-col gap-4"
      aria-labelledby={`day-${day.date}`}
    >
      <h2
        id={`day-${day.date}`}
        className="sticky top-[var(--header-height)] z-10 bg-background/90 py-2 text-lg font-bold backdrop-blur"
      >
        {formatFeedDay(day.date)}
      </h2>

      {shown.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Nichts zu deinen Themen an diesem Tag
          {hiddenCount > 0 &&
            ` · ${hiddenCount} ${hiddenCount === 1 ? 'weiteres Thema' : 'weitere Themen'}`}
          .
        </p>
      )}

      {shown.map(({ digest, votes }) => (
        <div key={digest.id} className="flex flex-col gap-2">
          <h3 className="text-sm font-semibold text-muted-foreground">
            {digest.parliament_name}
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-4">
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
            <div className="flex flex-col gap-4">
              {votes.length > 0 ? (
                votes.map((vote) => (
                  <VoteCard
                    key={vote.poll_id}
                    vote={vote}
                    onOpen={() => open(`${digest.id}:${vote.poll_id}`)}
                  />
                ))
              ) : (
                <p
                  className={cn(
                    CARD_PLACEHOLDER,
                    'p-4 text-sm text-muted-foreground',
                  )}
                >
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
