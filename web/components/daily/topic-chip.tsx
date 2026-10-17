import { topicColor } from '@/lib/daily/palette';
import { topicShortTitle, topicTitle } from '@/lib/daily/topics';
import { cn } from '@/lib/utils';
import { FOCUS_RING, META_TEXT, PILL, PILL_ACTIVE } from './card-styles';

export function TopicDot({ topic }: { topic: string }) {
  return (
    <span
      aria-hidden
      className="inline-block size-2.5 shrink-0 rounded-full"
      style={{ backgroundColor: topicColor(topic) }}
    />
  );
}

/** "● ● Gesundheit · Wirtschaft", optionally followed by more meta. */
export function TopicMeta({
  topics,
  suffix,
  short = false,
  className,
}: {
  topics: string[];
  suffix?: string | null;
  short?: boolean;
  className?: string;
}) {
  const title = short ? topicShortTitle : topicTitle;
  return (
    <p
      className={cn(META_TEXT, 'flex min-w-0 items-center gap-1.5', className)}
    >
      <span className="flex gap-1">
        {topics.map((topic) => (
          <TopicDot key={topic} topic={topic} />
        ))}
      </span>
      <span className="min-w-0 truncate">
        {[...topics.map(title), suffix].filter(Boolean).join(' · ')}
      </span>
    </p>
  );
}

type Props = {
  topic: string;
  active: boolean;
  onClick: () => void;
};

function TopicChip({ topic, active, onClick }: Props) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(PILL, FOCUS_RING, active && PILL_ACTIVE)}
    >
      <TopicDot topic={topic} />
      {topicShortTitle(topic)}
    </button>
  );
}

export default TopicChip;
