import { Button } from '@/components/ui/button';
import { DAILY_TOPICS } from '@/lib/daily/topics';
import { cn } from '@/lib/utils';

type Props = {
  topic: string;
  active?: boolean;
  onClick?: () => void;
};

/** Same look as the site's TopicTag, plus the digest-only `other` topic. */
function TopicChip({ topic, active = false, onClick }: Props) {
  const style = DAILY_TOPICS[topic] ?? DAILY_TOPICS.other;
  const base =
    'h-6 w-fit whitespace-nowrap rounded-md border px-2 py-0 text-xs';

  if (onClick) {
    return (
      <Button
        size="sm"
        variant="outline"
        aria-pressed={active}
        className={cn(
          base,
          'h-7',
          style.normal,
          style.hover,
          active && style.active,
        )}
        onClick={onClick}
      >
        {style.title}
      </Button>
    );
  }

  return (
    <span className={cn(base, 'flex items-center', style.normal)}>
      {style.title}
    </span>
  );
}

export default TopicChip;
