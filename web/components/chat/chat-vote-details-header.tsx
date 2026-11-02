import { LOCALE_INFO } from '@/i18n/locales';
import useCarouselCurrentIndex from '@/lib/hooks/use-carousel-current-index';
import type { Vote } from '@/lib/socket.types';
import { useLocale } from 'next-intl';
import { useMemo } from 'react';
import AnimateTextOverflow from './animate-text-overflow';

type Props = {
  votes: Vote[];
};

function ChatVoteDetailsHeader({ votes }: Props) {
  const locale = useLocale();
  const selectedIndex = useCarouselCurrentIndex();

  const vote = votes[selectedIndex];

  const formattedDate = useMemo(() => {
    return new Date(vote.date).toLocaleDateString(LOCALE_INFO[locale].intl, {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    });
  }, [vote.date, locale]);

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
