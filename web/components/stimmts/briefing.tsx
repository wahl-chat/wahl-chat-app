import { Button } from '@/components/ui/button';
import { formatDate } from '@/lib/stimmts/labels';
import type { Puzzle } from '@/lib/stimmts/types';

type Props = {
  puzzle: Puzzle;
  onStart: () => void;
};

function Briefing({ puzzle, onStart }: Props) {
  return (
    <section className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Abstimmung im Bundestag am {formatDate(puzzle.voteDate)}
      </p>
      <p className="leading-relaxed">{puzzle.briefing}</p>
      <p className="rounded-md bg-muted p-3 text-sm font-medium">
        {puzzle.yesMeans}
      </p>
      <p className="text-sm text-muted-foreground">
        Gleich siehst du die Parteien nacheinander, von links nach rechts, wie
        sie im Plenarsaal sitzen. Wie hat jede von ihnen abgestimmt? Einmal
        getippt, lässt sich eine Antwort nicht mehr ändern.
      </p>
      <Button size="lg" onClick={onStart}>
        Los geht&apos;s
      </Button>
    </section>
  );
}

export default Briefing;
