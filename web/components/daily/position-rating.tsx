'use client';

import type { PositionOpinion } from '@/lib/daily/opinions';
import { SEAT_FILLS } from '@/lib/daily/palette';
import { cn } from '@/lib/utils';
import { ArrowBigDownIcon, ArrowBigUpIcon } from 'lucide-react';
import { FOCUS_RING } from './card-styles';

const CHOICE_COLOR: Record<PositionOpinion, string> = {
  up: SEAT_FILLS.yes,
  down: SEAT_FILLS.no,
};

const ARROW_BUTTON = cn(
  FOCUS_RING,
  'flex size-9 items-center justify-center rounded-full text-[var(--daily-muted)] transition-colors hover:bg-[var(--daily-surface)]',
);

/**
 * "Stimmst du zu?" for one Fraktion's position: agree, the net score,
 * disagree. Tapping the chosen arrow again takes the opinion back. Before
 * the reader has opted in there is no score, and none is shown.
 */
export function PositionRating({
  partyName,
  choice,
  score,
  onChoose,
}: {
  partyName: string;
  choice: PositionOpinion | undefined;
  score: number | null;
  onChoose: (value: PositionOpinion | null) => void;
}) {
  const toggle = (value: PositionOpinion) =>
    onChoose(choice === value ? null : value);
  const color = choice ? CHOICE_COLOR[choice] : undefined;
  return (
    <div
      role="group"
      aria-label={`Position von ${partyName} bewerten`}
      className="-mr-2 inline-flex shrink-0 items-center"
    >
      <button
        type="button"
        aria-label="Stimme zu"
        aria-pressed={choice === 'up'}
        onClick={() => toggle('up')}
        className={ARROW_BUTTON}
        style={choice === 'up' ? { color } : undefined}
      >
        <ArrowBigUpIcon
          className="size-5"
          fill={choice === 'up' ? 'currentColor' : 'none'}
        />
      </button>
      {score !== null && (
        <span
          className="min-w-6 text-center text-[14px] font-bold tabular-nums"
          style={{ color }}
        >
          {score}
        </span>
      )}
      <button
        type="button"
        aria-label="Stimme nicht zu"
        aria-pressed={choice === 'down'}
        onClick={() => toggle('down')}
        className={ARROW_BUTTON}
        style={choice === 'down' ? { color } : undefined}
      >
        <ArrowBigDownIcon
          className="size-5"
          fill={choice === 'down' ? 'currentColor' : 'none'}
        />
      </button>
    </div>
  );
}
