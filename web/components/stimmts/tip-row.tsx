import { FOCUS_RING } from '@/components/daily/card-styles';
import { ANSWER_LABELS, partyLabel } from '@/lib/stimmts/labels';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { cn } from '@/lib/utils';
import PartyTile from './party-tile';
import VoteDot from './vote-dot';

type Props = {
  puzzle: Puzzle;
  guesses: Guesses;
  /** The party being asked, ringed; null on the review. */
  current: string | null;
  onEdit: (partyId: string) => void;
};

/**
 * The five parties in seating order, each with the player's tip under it.
 * Until the reveal any answered party can be tapped to change its tip; a
 * party still to come has nothing to change, so it is dimmed and inert.
 */
function TipRow({ puzzle, guesses, current, onEdit }: Props) {
  return (
    <ul className="flex justify-between gap-1">
      {puzzle.parties.map(({ partyId }) => {
        const guess = guesses[partyId];
        const isCurrent = partyId === current;
        const face = (
          <>
            <span
              className={cn(
                'rounded-sm',
                isCurrent &&
                  'outline outline-2 outline-offset-2 outline-[var(--daily-ink)]',
              )}
            >
              <PartyTile partyId={partyId} size="sm" />
            </span>
            {/* Keeps its place while empty, so the tiles never shift. */}
            <span aria-hidden className="flex h-2.5 items-center">
              {guess && <VoteDot kind={guess} ring />}
            </span>
          </>
        );
        return (
          <li key={partyId} className="flex">
            {guess ? (
              <button
                type="button"
                aria-label={`${partyLabel(partyId)}: ${ANSWER_LABELS[guess]}. Ändern`}
                aria-current={isCurrent ? 'step' : undefined}
                onClick={() => onEdit(partyId)}
                className={cn(
                  'flex min-h-11 min-w-11 flex-col items-center gap-1.5 rounded-md p-1 transition-colors hover:bg-[var(--daily-surface)]',
                  FOCUS_RING,
                )}
              >
                {face}
              </button>
            ) : (
              <span
                aria-hidden
                className={cn(
                  'flex min-h-11 min-w-11 flex-col items-center gap-1.5 p-1',
                  !isCurrent && 'opacity-40',
                )}
              >
                {face}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default TipRow;
