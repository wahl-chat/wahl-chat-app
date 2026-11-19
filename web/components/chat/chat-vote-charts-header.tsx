import { Separator } from '@/components/ui/separator';
import useCarouselCurrentIndex from '@/lib/hooks/use-carousel-current-index';
import type { Vote } from '@/lib/socket.types';
import { useTranslations } from 'next-intl';
import OverallVoteChart from './overall-vote-chart';
import PartiesVoteChart from './parties-vote-chart';

type Props = {
  votes: Vote[];
};

function ChatVoteChartsHeader({ votes }: Props) {
  const t = useTranslations('chat.votes');
  const selectedIndex = useCarouselCurrentIndex();

  const vote = votes[selectedIndex];

  return (
    <>
      <div className="mb-0 mt-8 grid grid-cols-2 justify-center gap-0 px-4 md:mt-12 md:flex">
        <OverallVoteChart vote={vote} />
        <Separator
          orientation="vertical"
          className="my-auto hidden h-[100px] md:block"
        />
        <PartiesVoteChart vote={vote} />
      </div>

      <div className="mt-4 flex flex-row flex-wrap items-center justify-center gap-4 p-4 text-sm text-muted-foreground">
        <p>
          <span className="mr-2 inline-block size-2 rounded-full bg-[hsl(var(--chart-yes))]" />
          {t('yes')}
        </p>
        <p>
          <span className="mr-2 inline-block size-2 rounded-full bg-[hsl(var(--chart-no))]" />
          {t('no')}
        </p>
        <p>
          <span className="mr-2 inline-block size-2 rounded-full bg-[hsl(var(--chart-abstain))]" />
          {t('abstain')}
        </p>
        <p>
          <span className="mr-2 inline-block size-2 rounded-full bg-[hsl(var(--chart-not-voted))]" />
          {t('notVoted')}
        </p>
      </div>

      <Separator className="mt-2" />
    </>
  );
}

export default ChatVoteChartsHeader;
