import { shortDay } from '@/lib/stimmts/labels';
import { periodSeats } from '@/lib/stimmts/logo';
import {
  PERIOD_LENGTH,
  type Wahlperiode as Period,
  type PlayedDay,
} from '@/lib/stimmts/period';
import type { Streak } from '@/lib/stimmts/streak';
import { type Ref, useState } from 'react';
import Countdown from './countdown';
import PeriodChamber from './period-chamber';

const dayCount = (days: number) => `${days} ${days === 1 ? 'Tag' : 'Tage'}`;

type Props = {
  period: Period;
  streak: Streak;
  /** The urn's slot, which the Stimmkarte flies into. */
  slotRef?: Ref<HTMLSpanElement>;
  /** Today's seat just filled: it pops in. */
  justCast?: boolean;
};

/**
 * The player's Wahlperiode: the urn's slot on top, one seat per day below,
 * the day in the hollow centre and, once today's card is in, the countdown
 * right under the seats. It is the streak and the collection in one: a
 * played seat shows that day's card when tapped.
 */
function Wahlperiode({ period, streak, slotRef, justCast = false }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const seats = periodSeats(period.days, period.todayInHand);
  const shown = selected === null ? undefined : period.days[selected];

  return (
    <section aria-label="Deine Wahlperiode" className="flex flex-col gap-2">
      <div
        aria-hidden
        className="mx-auto flex h-[26px] w-[70%] items-center justify-center rounded-b-[3px] rounded-t-lg bg-foreground"
      >
        <span
          ref={slotRef}
          className="h-[5px] w-[64%] rounded-full bg-background"
        />
      </div>
      <div className="relative px-6 pt-3">
        <PeriodChamber
          seats={seats}
          complete={period.complete}
          selected={selected}
          fresh={justCast ? period.days.length - 1 : null}
          onSelect={(index) =>
            setSelected((current) => (current === index ? null : index))
          }
        />
        <div className="absolute bottom-0 left-1/2 flex -translate-x-1/2 flex-col items-center whitespace-nowrap text-center">
          <span className="font-display text-[30px] font-extrabold tabular-nums leading-[34px] tracking-[-0.02em]">
            Tag {period.day}
          </span>
          <span className="text-xs font-medium text-muted-foreground">
            von {PERIOD_LENGTH}
          </span>
        </div>
      </div>
      {!period.todayInHand && <Countdown />}
      <p className="flex flex-wrap justify-between gap-x-3 gap-y-0.5 text-[13px] leading-[18px] text-muted-foreground">
        <span>
          <strong className="font-semibold text-foreground">
            {dayCount(streak.current)}
          </strong>{' '}
          in Folge · Rekord {dayCount(streak.best)}
        </span>
        <span>
          Wahlperiode {period.index} · Tag {period.day} von {PERIOD_LENGTH}
        </span>
      </p>
      {shown?.kind === 'played' ? (
        <DayCard day={shown} />
      ) : (
        <p className="text-center text-xs text-muted-foreground">
          Tippe auf einen Sitz, um die Stimmkarte des Tages zu sehen.
        </p>
      )}
    </section>
  );
}

/** A past day's card, small, as shown when its seat is tapped. */
function DayCard({ day }: { day: PlayedDay }) {
  return (
    <div
      role="group"
      aria-label={`Stimmkarte Nummer ${day.number}, ${day.score} von 5 richtig`}
      className="flex animate-stimmts-screen items-center gap-3 rounded-lg bg-foreground px-3 py-2 text-background motion-reduce:animate-none"
    >
      <span className="whitespace-nowrap font-display text-lg font-extrabold leading-[22px]">
        Nr. {day.number}
      </span>
      <span className="min-w-0 flex-1 truncate text-[13px] leading-[18px] opacity-80">
        {shortDay(day.playDate)} · {day.topic}
      </span>
      <span className="-rotate-6 rounded-sm border-2 border-brand-red px-1.5 font-display text-sm font-extrabold leading-[18px] text-brand-red">
        {day.score}/5
      </span>
    </div>
  );
}

export default Wahlperiode;
