import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { type Topic, TOPIC_TITLES } from './topics.data';

type Props = {
  topic: Topic;
  active?: boolean;
  onClick?: () => void;
};

function TopicTag({ topic, active = false, onClick }: Props) {
  const { title, normal, hover, active: activeStyle } = TOPIC_TITLES[topic];

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
