import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTranslations } from 'next-intl';
import { TOPIC_TITLES, type Topic } from './topics.data';

type Props = {
  topic: Topic;
  active?: boolean;
  onClick?: () => void;
};

function TopicTag({ topic, active = false, onClick }: Props) {
  const t = useTranslations('topics');
  const { normal, hover, active: activeStyle } = TOPIC_TITLES[topic];
  const title = t(`${topic}.title`);

  if (onClick) {
    return (
      <Button
        size="sm"
        variant="outline"
        className={cn(
          'border rounded-md px-2 py-0 w-fit whitespace-nowrap h-7 text-xs',
          normal,
          hover,
          active && activeStyle,
        )}
        onClick={onClick}
      >
        {title}
      </Button>
    );
  }

  return (
    <span
      className={cn(
        'border rounded-md px-2 py-0 w-fit whitespace-nowrap h-7 text-xs flex items-center justify-center',
        normal,
        active && activeStyle,
      )}
    >
      {title}
    </span>
  );
}

export default TopicTag;
