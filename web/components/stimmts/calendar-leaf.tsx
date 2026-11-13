import { dayOfMonth, monthShort } from '@/lib/stimmts/labels';
import { cn } from '@/lib/utils';

type Props = {
  isoDate: string;
  /** The bill sheet draws it on paper instead of the page's card colour. */
  onPaper?: boolean;
};

/** A calendar leaf for the day of the vote: the month on top, the day large. */
function CalendarLeaf({ isoDate, onPaper = false }: Props) {
  return (
    <div
      aria-hidden
      className={cn(
        'flex w-12 flex-none flex-col overflow-hidden rounded-md border text-center',
        onPaper ? 'border-paper-rule bg-paper' : 'bg-card',
      )}
    >
      <span className="bg-primary text-[11px] font-bold uppercase leading-[18px] tracking-[0.06em] text-primary-foreground">
        {monthShort(isoDate)}
      </span>
      <span className="font-display text-[22px] font-extrabold tabular-nums leading-[30px]">
        {dayOfMonth(isoDate)}
      </span>
    </div>
  );
}

export default CalendarLeaf;
