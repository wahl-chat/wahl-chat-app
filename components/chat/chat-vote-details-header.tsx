import { useMemo } from 'react';
import type { Vote } from '@/lib/socket.types';
import useCarouselCurrentIndex from '@/lib/hooks/use-carousel-current-index';
import AnimateTextOverflow from './animate-text-overflow';

type Props = {
  votes: Vote[];
};

function ChatVoteDetailsHeader({ votes }: Props) {
  const selectedIndex = useCarouselCurrentIndex();

  const vote = votes[selectedIndex];

  const formattedDate = useMemo(() => {
    return new Date(vote.date).toLocaleDateString('de-DE', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    });
  }, [vote.date]);

  return (
    <div className="border-b border-border pb-4 pt-6 text-center md:text-left">
      <AnimateTextOverflow>{vote.title}</AnimateTextOverflow>
      <p className="text-center text-xs text-muted-foreground">
        {formattedDate}
      </p>
    </div>
  );
}

export default ChatVoteDetailsHeader;
