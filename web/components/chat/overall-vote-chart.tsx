import type { Vote } from '@/lib/socket.types';
import { useTranslations } from 'next-intl';
import { useMemo } from 'react';
import VoteChart from './vote-chart';

type Props = {
  vote: Vote;
};

function OverallVoteChart({ vote }: Props) {
  const t = useTranslations('chat.votes');
  const [resultStatement, percentageStatement] = useMemo(() => {
    const { yes, no, abstain } = vote.voting_results.overall;

    const totalVotes = yes + no + abstain;

    if (totalVotes === 0) {
      return [t('noValidVotes'), t('noResults')];
    }

    let outcome: 'accepted' | 'rejected' | 'tie';
    let percentage: number;

    if (yes > no) {
      outcome = 'accepted';
      percentage = (yes / totalVotes) * 100;
    } else if (no > yes) {
      outcome = 'rejected';
      percentage = (no / totalVotes) * 100;
    } else {
      outcome = 'tie';
      percentage = (no / totalVotes) * 100;
    }

    const resultStatement = t.rich('outcome', {
      outcome,
      bold: (chunks) => <span className="font-bold">{chunks}</span>,
    });

    const percentageStatement = t('outcomePercentage', {
      outcome,
      percentage: percentage.toFixed(1),
    });

    return [resultStatement, percentageStatement];
  }, [vote.voting_results.overall, t]);

  return (
    <section className="flex flex-1 flex-col items-center justify-center gap-4">
      <VoteChart
        voteResults={vote.voting_results.overall}
        memberCount={vote.voting_results.overall.members}
      />

      <div className="flex flex-col items-center justify-center text-center">
        <p>{resultStatement}</p>
        <p className="text-xs text-muted-foreground">{percentageStatement}</p>
      </div>
    </section>
  );
}

export default OverallVoteChart;
