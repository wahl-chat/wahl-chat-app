import type { Vote } from '@/lib/socket.types';
import OverallVoteChart from './overall-vote-chart';
import { Separator } from '@/components/ui/separator';
import PartiesVoteChart from './parties-vote-chart';
import useCarouselCurrentIndex from '@/lib/hooks/use-carousel-current-index';

type Props = {
  votes: Vote[];
};

function ChatVoteChartsHeader({ votes }: Props) {
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
          Ja
        </p>
        <p>
          <span className="mr-2 inline-block size-2 rounded-full bg-[hsl(var(--chart-no))]" />
          Nein
        </p>
        <p>
          <span className="mr-2 inline-block size-2 rounded-full bg-[hsl(var(--chart-abstain))]" />
          Enthaltung
        </p>
        <p>
          <span className="mr-2 inline-block size-2 rounded-full bg-[hsl(var(--chart-not-voted))]" />
          Nicht abgestimmt
        </p>
      </div>

      <Separator className="mt-2" />
    </>
  );
}

export default ChatVoteChartsHeader;
