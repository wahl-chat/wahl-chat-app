import { cn } from '@/lib/utils';
import { CARD_SURFACE } from './card-styles';

const BLOCK = 'animate-pulse rounded bg-[var(--daily-surface)]';

function CardSkeleton({ media }: { media?: boolean }) {
  return (
    <div className={cn(CARD_SURFACE, 'flex flex-col overflow-hidden')}>
      {media && <div className={cn(BLOCK, 'aspect-video rounded-none')} />}
      <div className="flex flex-col gap-2 p-4">
        <div className={cn(BLOCK, 'h-3 w-1/3')} />
        <div className={cn(BLOCK, 'h-5 w-11/12')} />
        <div className={cn(BLOCK, 'h-5 w-2/3')} />
        <div className={cn(BLOCK, 'mt-1 h-3.5 w-full')} />
        <div className={cn(BLOCK, 'h-3.5 w-5/6')} />
      </div>
    </div>
  );
}

/** A sitting day's shape while older days load: the Hot Topic, then the
 * start of the day's swipe row, so the feed does not jump when it arrives. */
function DaySkeleton() {
  return (
    <div
      aria-busy="true"
      aria-label="Ältere Tage laden"
      className="flex w-full flex-col gap-8"
    >
      <div aria-hidden className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className={cn(BLOCK, 'h-5 w-28')} />
          <div className={cn(BLOCK, 'h-3 w-32')} />
        </div>
        <CardSkeleton media />
      </div>
      <div aria-hidden className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <div className={cn(BLOCK, 'h-3 w-40')} />
          <div className={cn(BLOCK, 'h-5 w-48')} />
        </div>
        <div className="-mx-4 flex gap-3 overflow-hidden px-4">
          <div className="w-[86%] shrink-0 md:w-[48%]">
            <CardSkeleton />
          </div>
          <div className="w-[86%] shrink-0 md:w-[48%]">
            <CardSkeleton />
          </div>
        </div>
      </div>
    </div>
  );
}

export default DaySkeleton;
