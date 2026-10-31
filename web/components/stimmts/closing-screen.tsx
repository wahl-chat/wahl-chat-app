import { BASE_URL } from '@/lib/seo';
import { trackResultShared } from '@/lib/stimmts/analytics';
import { periodSeats } from '@/lib/stimmts/logo';
import {
  type DayRecord,
  PERIOD_LENGTH,
  summarizePeriod,
} from '@/lib/stimmts/period';
import { buildClosingShareText } from '@/lib/stimmts/share';
import FeedbackPrompt from './feedback-prompt';
import PeriodChamber from './period-chamber';
import ShareButton from './share-button';
import StatusScreen from './status-screen';

type Props = {
  /** Every day of the run, played or missed (see dayRecords). */
  days: DayRecord[];
  onOpenDay: (number: number) => void;
};

/**
 * After the last puzzle. It reports what the player did in numbers and never
 * says "you played them all", since most players will have missed days. A
 * player who never played gets the message alone.
 */
function ClosingScreen({ days, onOpenDay }: Props) {
  const last = days.length;
  // The run's last Wahlperiode, with every day of it settled.
  const periodDays = days.slice(-(((last - 1) % PERIOD_LENGTH) + 1));
  const complete =
    periodDays.length === PERIOD_LENGTH &&
    periodDays.every((day) => day.kind === 'played');
  const summary = summarizePeriod(days);

  return (
    <StatusScreen
      title="Die Wahlperiode ist vorbei"
      text={`Alle ${last} Rätsel dieser Runde sind gelaufen. Mehr Rätsel sind in Arbeit. Bleib dran!`}
    >
      {summary.played > 0 && (
        <div className="flex w-full flex-col items-center gap-8">
          <div className="flex w-full flex-col items-center gap-3">
            <PeriodChamber
              seats={periodSeats(periodDays, false)}
              complete={complete}
              // One past the last day: no seat is "today", every seat opens.
              today={last + 1}
              onOpen={onOpenDay}
              className="mx-auto max-w-[300px]"
            />
            <p className="text-sm text-muted-foreground">
              <span className="font-display text-2xl font-extrabold tabular-nums text-foreground">
                {summary.played}/{last}
              </span>{' '}
              Tage gespielt ·{' '}
              <span className="font-display text-2xl font-extrabold tabular-nums text-foreground">
                {summary.correct}/{summary.possible}
              </span>{' '}
              richtig
            </p>
          </div>
          <ShareButton
            text={buildClosingShareText({
              summary,
              days: last,
              url: `${BASE_URL}/stimmts`,
            })}
            onShared={(method) => trackResultShared('closing', method)}
          />
          <FeedbackPrompt />
        </div>
      )}
    </StatusScreen>
  );
}

export default ClosingScreen;
