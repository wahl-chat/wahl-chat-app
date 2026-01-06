import type { Vote } from '@/lib/socket.types';
import { useMemo } from 'react';
import VoteChart from './vote-chart';

type Props = {
  vote: Vote;
};

function OverallVoteChart({ vote }: Props) {
  const [resultStatement, percentageStatement] = useMemo(() => {
    const { yes, no, abstain } = vote.voting_results.overall;

    const totalVotes = yes + no + abstain;

    if (totalVotes === 0) {
      return [
        'Keine gültigen Stimmen abgegeben',
        'Es konnten keine Ergebnisse ermittelt werden',
      ];
    }

    let outcome: string;
    let percentage: number;

    if (yes > no) {
      outcome = 'angenommen';
      percentage = (yes / totalVotes) * 100;
    } else if (no > yes) {
      outcome = 'abgelehnt';
      percentage = (no / totalVotes) * 100;
    } else {
      outcome = 'unentschieden';
      percentage = (no / totalVotes) * 100;
    }

    const resultStatement = (
      <>
        Antrag wurde{' '}
        <span className="font-bold">
          {outcome.charAt(0).toUpperCase() + outcome.slice(1)}.
        </span>
      </>
    );

    let percentageStatement: string;
    if (outcome === 'unentschieden') {
      percentageStatement = `Antrag wurde unentschieden mit jeweils ${percentage.toFixed(
        1,
      )}% der Stimmen.`;
    } else {
      percentageStatement = `Antrag wurde mit ${percentage.toFixed(1)}% der Stimmen ${outcome}.`;
    }

    return [resultStatement, percentageStatement];
  }, [vote.voting_results.overall]);

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
