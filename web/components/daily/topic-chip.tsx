import { topicColor } from '@/lib/daily/palette';
import { topicShortTitle } from '@/lib/daily/topics';
import { cn } from '@/lib/utils';
import type { ReactNode } from 'react';
import { FOCUS_RING, META_TEXT, PILL, PILL_ACTIVE } from './card-styles';
import { useFeedLocale } from './feed-locale';

export function TopicDot({ topic }: { topic: string }) {
  return (
    <span
      aria-hidden
      className="inline-block size-2.5 shrink-0 rounded-full"
      style={{ backgroundColor: topicColor(topic) }}
    />
  );
}

/** "● ● Gesundheit · Wirtschaft", optionally followed by more meta. Each
 * topic carries the label of its filter pill, so a card names exactly the
 * filters it appears under. */
export function TopicMeta({
  topics,
  suffix,
  trailing,
  className,
}: {
  topics: string[];
  suffix?: string | null;
  /** Non-text meta after the line, e.g. the heat dots; never truncated. */
  trailing?: ReactNode;
  className?: string;
}) {
  const { locale } = useFeedLocale();
  const title = (topic: string) => topicShortTitle(topic, locale);
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
      {trailing && (
        <>
          <span aria-hidden>·</span>
          <span className="flex shrink-0 items-center">{trailing}</span>
        </>
      )}
    </p>
  );
}

type Props = {
  topic: string;
  active: boolean;
  onClick: () => void;
};

function TopicChip({ topic, active, onClick }: Props) {
  const { locale } = useFeedLocale();
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(PILL, FOCUS_RING, active && PILL_ACTIVE)}
    >
      <TopicDot topic={topic} />
      {topicShortTitle(topic, locale)}
    </button>
  );
}

export default TopicChip;
