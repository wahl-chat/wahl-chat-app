import { seatCount } from '@/lib/stimmts/hemicycle';
import { formatDate, timeAgo, weekdayName } from '@/lib/stimmts/labels';
import type { Puzzle } from '@/lib/stimmts/types';
import BillSheet from './bill-sheet';
import CalendarLeaf from './calendar-leaf';
import Hemicycle from './hemicycle';
import StartButton from './start-button';
import Stimmkarte from './stimmkarte';
import YesMeans from './yes-means';

type Props = {
  number: number;
  playDate: string;
  puzzle: Puzzle;
  onStart: () => void;
};

/**
 * The first screen, read top to bottom: the player's Stimmkarte, the bill,
 * then the chamber the player is about to fill, with "Los geht's" right
 * under it. It never hints at the outcome.
 */
function Briefing({ number, playDate, puzzle, onStart }: Props) {
  const seats =
    puzzle.parties.reduce((sum, party) => sum + seatCount(party), 0) +
    puzzle.unaffiliated;

  return (
    <div className="flex flex-col gap-4">
      <Stimmkarte
        number={number}
        playDate={playDate}
        title={puzzle.title}
        topic={puzzle.topic}
      />
      {puzzle.document ? (
        <BillSheet
          document={puzzle.document}
          briefing={puzzle.briefing}
          voteDate={puzzle.voteDate}
          playDate={playDate}
          yesMeans={puzzle.yesMeans}
        />
      ) : (
        <PlainBriefing puzzle={puzzle} playDate={playDate} />
      )}
      <Hemicycle
        parties={puzzle.parties}
        unaffiliated={puzzle.unaffiliated}
        states={{}}
        center={{ big: String(seats), small: 'Sitze' }}
      />
      <StartButton onStart={onStart} />
    </div>
  );
}

/** Without a verified Drucksache: the date, the summary and the Ja line. */
function PlainBriefing({
  puzzle,
  playDate,
}: {
  puzzle: Puzzle;
  playDate: string;
}) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <CalendarLeaf isoDate={puzzle.voteDate} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="text-sm font-medium">
            Namentliche Abstimmung im Bundestag
          </p>
          <p className="text-sm text-muted-foreground">
            {weekdayName(puzzle.voteDate)}, {formatDate(puzzle.voteDate)} ·{' '}
            {timeAgo(puzzle.voteDate, playDate)}
          </p>
        </div>
      </div>
      <p lang="de" className="hyphens-auto text-justify leading-relaxed">
        {puzzle.briefing}
      </p>
      <YesMeans yesMeans={puzzle.yesMeans} />
    </section>
  );
}

export default Briefing;
