import useCarouselCurrentIndex from '@/lib/hooks/use-carousel-current-index';
import type { Vote } from '@/lib/socket.types';

type Props = {
  votes: Vote[];
};

function ChatVoteDetailsSlideCounter({ votes }: Props) {
  const selectedIndex = useCarouselCurrentIndex();

  return (
    <div className="flex flex-col items-center justify-center">
      <p className="text-sm font-bold">
        {selectedIndex + 1} / {votes.length}
      </p>
      <span className="text-xs text-muted-foreground">Abstimmungen</span>
    </div>
  );
}

export default ChatVoteDetailsSlideCounter;
