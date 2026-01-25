import { cn } from '@/lib/utils';

type Props = {
  partyCount: number;
  className?: string;
  gridColumns?: number;
};

function LoadingPartyCards({ partyCount, className, gridColumns }: Props) {
  return (
    <section
      className={cn('grid w-full gap-2', className)}
      style={{
        gridTemplateColumns: `repeat(${gridColumns}, minmax(0, 1fr))`,
      }}
    >
      {Array.from({ length: partyCount }).map((_, index) => (
        <div
          // biome-ignore lint/suspicious/noArrayIndexKey: <explanation>
          key={index}
          className={cn(
            'flex aspect-square items-center justify-center transition-all rounded-md',
            'bg-zinc-200 dark:bg-zinc-700 w-full h-fit p-6 border border-muted-foreground/20 overflow-hidden',
            'animate-pulse',
          )}
        />
      ))}
    </section>
  );
}

export default LoadingPartyCards;
