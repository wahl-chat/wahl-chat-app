import { topicSwatch } from '@/lib/daily/palette';
import { topicTitle } from '@/lib/daily/topics';
import { cn } from '@/lib/utils';

type Props = {
  topic: string;
  active?: boolean;
  onClick?: () => void;
};

/**
 * Display mode: a flat ink-framed label in the topic colour.
 * Filter mode: a mechanical key that lifts when idle and sits pressed in
 * (inset shadow, offset into its own shadow) while selected.
 */
function TopicChip({ topic, active = false, onClick }: Props) {
  const swatch = topicSwatch(topic);
  const title = topicTitle(topic);

  if (onClick) {
    return (
      <button
        type="button"
        aria-pressed={active}
        onClick={onClick}
        style={
          active
            ? { backgroundColor: swatch.fill, color: swatch.fg }
            : undefined
        }
        className={cn(
          'flex h-8 items-center gap-1.5 whitespace-nowrap rounded-[4px] border-2 border-[var(--daily-ink)] px-2.5 text-xs transition-[transform,box-shadow] duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--daily-ink)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--daily-canvas)] motion-reduce:transition-none',
          active
            ? 'translate-x-[2px] translate-y-[2px] font-bold shadow-[inset_2px_2px_4px_rgba(0,0,0,0.25)]'
            : 'bg-[var(--daily-surface)] font-medium shadow-[2px_2px_0_0_var(--daily-ink)] hover:-translate-x-px hover:-translate-y-px hover:shadow-[3px_3px_0_0_var(--daily-ink)] motion-reduce:transform-none',
        )}
      >
        {!active && (
          <span
            aria-hidden
            className="size-2.5 rounded-[2px] border border-[var(--daily-ink)]"
            style={{ backgroundColor: swatch.fill }}
          />
        )}
        {title}
      </button>
    );
  }

  return (
    <span
      className="flex h-6 w-fit items-center whitespace-nowrap rounded-[4px] border-[1.5px] border-[#1A1A1A] px-2 text-[11px] font-semibold"
      style={{ backgroundColor: swatch.fill, color: swatch.fg }}
    >
      {title}
    </span>
  );
}

export default TopicChip;
