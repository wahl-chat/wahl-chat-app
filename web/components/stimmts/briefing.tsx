import { formatDate, timeAgo, weekdayName } from '@/lib/stimmts/labels';
import type { Puzzle } from '@/lib/stimmts/types';
import BillSheet from './bill-sheet';
import CalendarLeaf from './calendar-leaf';
import YesMeans from './yes-means';

/** What the vote is about: the bill sheet, or the plain layout without one. */
export function BriefingSheet({
  puzzle,
  playDate,
}: {
  puzzle: Puzzle;
  playDate: string;
}) {
  return puzzle.document ? (
    <BillSheet
      document={puzzle.document}
      briefing={puzzle.briefing}
      voteDate={puzzle.voteDate}
      playDate={playDate}
      yesMeans={puzzle.yesMeans}
    />
  ) : (
    <PlainBriefing puzzle={puzzle} playDate={playDate} />
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
          <p className="text-sm text-[var(--daily-muted)]">
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
