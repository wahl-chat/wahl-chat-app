import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from '@/components/ui/chart';
import NumberFlow from '@number-flow/react';
import { Pie, PieChart } from 'recharts';

type Props = {
  voteResults: {
    yes: number;
    no: number;
    abstain: number;
    not_voted: number;
  };

  memberCount: number;
};

const chartConfig = {
  not_voted: {
    label: 'Nicht abgestimmt',
    color: 'hsl(var(--chart-1))',
  },
  abstain: {
    label: 'Enthaltung',
    color: 'hsl(var(--chart-2))',
  },
  no: {
    label: 'Nein',
    color: 'hsl(var(--chart-3))',
  },
  yes: {
    label: 'Ja',
    color: 'hsl(var(--chart-4))',
  },
} satisfies ChartConfig;

function VoteChart({ voteResults, memberCount }: Props) {
  const chartData = [
    {
      voteType: 'yes',
      result: voteResults.yes,
      fill: 'hsl(var(--chart-yes))',
    },
    {
      voteType: 'no',
      result: voteResults.no,
      fill: 'hsl(var(--chart-no))',
    },
    {
      voteType: 'abstain',
      result: voteResults.abstain,
      fill: 'hsl(var(--chart-abstain))',
    },
    {
      voteType: 'not_voted',
      result: voteResults.not_voted,
      fill: 'hsl(var(--chart-not-voted))',
    },
  ];

  return (
    <div className="relative size-[150px]">
      <ChartContainer config={chartConfig} className="relative z-20 size-full">
        <PieChart>
          <ChartTooltip
            cursor={false}
            content={<ChartTooltipContent hideLabel />}
          />
          <Pie
            data={chartData}
            dataKey="result"
            nameKey="voteType"
            innerRadius={50}
            outerRadius={75}
            strokeWidth={5}
          />
        </PieChart>
      </ChartContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <NumberFlow className="text-lg font-bold" value={memberCount} />
        <p className="text-xs text-muted-foreground">Mitglieder</p>
      </div>
    </div>
  );
}

export default VoteChart;
