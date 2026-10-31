import { yesMeaning } from '@/lib/stimmts/labels';
import { cn } from '@/lib/utils';
import VoteDot from './vote-dot';

/** The "Ja" key that leads every "bedeutet: …" line. */
export function YesKey({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex h-[22px] flex-none items-center gap-1.5 rounded-full bg-muted px-2 font-sans text-[13px] font-bold',
        className,
      )}
    >
      <VoteDot kind="yes" />
      Ja
    </span>
  );
}

/** What "Ja" means for this vote, as one slim line. */
function YesMeans({ yesMeans }: { yesMeans: string }) {
  return (
    <p className="flex items-start gap-3 rounded-md border p-3 text-[15px] leading-[22px]">
      <YesKey />
      <span>bedeutet: {yesMeaning(yesMeans)}</span>
    </p>
  );
}

export default YesMeans;
