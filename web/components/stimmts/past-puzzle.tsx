import { Button } from '@/components/ui/button';
import { chamberCenter, chamberStates } from '@/lib/stimmts/game-view';
import { scorePuzzle } from '@/lib/stimmts/score';
import type { Guesses, Puzzle } from '@/lib/stimmts/types';
import { useMemo } from 'react';
import { BriefingSheet } from './briefing';
import ChamberLegend from './chamber-legend';
import Hemicycle from './hemicycle';
import Reveal from './reveal';
import Stimmkarte from './stimmkarte';

type Props = {
  number: number;
  playDate: string;
  puzzle: Puzzle;
  /** The player's tips, or null for a day they missed. */
  guesses: Guesses | null;
  onBack: () => void;
};

/**
 * A past day's puzzle, already turned over: what the vote was about, how the
 * parties voted and, for a day the player played, their tips and score. It
 * cannot be answered, so it never adds a card to the urn.
 */
function PastPuzzle({ number, playDate, puzzle, guesses, onBack }: Props) {
  const all = useMemo(
    () => new Set(puzzle.parties.map((party) => party.partyId)),
    [puzzle],
  );
  const tips = guesses ?? {};

  return (
    <div className="flex flex-col gap-4 py-6">
      <Button
        variant="ghost"
        size="sm"
        onClick={onBack}
        className="-ml-3 self-start"
      >
        ← Zurück zu heute
      </Button>
      <Stimmkarte
        number={number}
        playDate={playDate}
        title={puzzle.title}
        topic={puzzle.topic}
        score={guesses ? scorePuzzle(puzzle, guesses).correct : undefined}
      />
      {!guesses && (
        <p className="text-center text-sm text-muted-foreground">
          Dieses Rätsel hast du verpasst.
        </p>
      )}
      <BriefingSheet puzzle={puzzle} playDate={playDate} />
      <Hemicycle
        parties={puzzle.parties}
        unaffiliated={puzzle.unaffiliated}
        states={chamberStates(puzzle, 'reveal', tips, all)}
        center={chamberCenter(puzzle, 'reveal', tips, all)}
      />
      <ChamberLegend kind="votes" unaffiliated={puzzle.unaffiliated} />
      <Reveal puzzle={puzzle} guesses={tips} revealed={all} />
      <Button variant="outline" size="lg" className="w-full" onClick={onBack}>
        Zurück zu heute
      </Button>
    </div>
  );
}

export default PastPuzzle;
