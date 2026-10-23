'use client';

import {
  type Phase,
  chamberCenter,
  chamberStates,
} from '@/lib/stimmts/game-view';
import { getGame } from '@/lib/stimmts/progress';
import type { Puzzle } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useReducedMotion } from 'motion/react';
import { useCallback, useEffect, useRef, useState } from 'react';
import Briefing from './briefing';
import ChamberLegend from './chamber-legend';
import GuessStep from './guess-step';
import Hemicycle from './hemicycle';
import Result from './result';
import Reveal from './reveal';

/** "Alle aufdecken" turns the parties over one after another, left to right. */
const REVEAL_ALL_STEP_MS = 450;

type Props = {
  number: number;
  puzzle: Puzzle;
  /** Today's Berlin date: the puzzle's day, and the day answers are saved on. */
  today: string;
};

/**
 * One puzzle from briefing to result. Which screen shows is derived from the
 * saved answers, so reloading the page resumes exactly where the player was.
 * The chamber is the board: it stays on top while the player answers and
 * while the parties are turned over.
 */
function PuzzleGame({ number, puzzle, today }: Props) {
  const game = useProgress((state) => getGame(state.progress, puzzle.id));
  const reduceMotion = useReducedMotion() ?? false;
  const [started, setStarted] = useState(false);
  // A game that was already finished when the page opened shows its result
  // straight away instead of replaying the reveal.
  const [alreadyFinished] = useState(game.finishedOn !== null);
  const [showResult, setShowResult] = useState(alreadyFinished);
  const [revealed, setRevealed] = useState<ReadonlySet<string>>(
    () =>
      new Set(
        alreadyFinished ? puzzle.parties.map((party) => party.partyId) : [],
      ),
  );

  // The score is stamped on with a bounce once, not on every return from
  // "Abstimmung ansehen" or after a reload.
  const stamped = useRef(alreadyFinished);
  useEffect(() => {
    if (showResult) {
      stamped.current = true;
    }
  });

  const finished = game.finishedOn !== null;
  const hasAnswers = Object.keys(game.guesses).length > 0;
  const phase: Phase = finished
    ? showResult
      ? 'result'
      : 'reveal'
    : started || hasAnswers
      ? 'answering'
      : 'briefing';

  const goTop = useCallback(() => {
    window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
  }, [reduceMotion]);

  const reveal = useCallback((partyId: string) => {
    setRevealed((previous) => new Set(previous).add(partyId));
  }, []);

  const revealTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  useEffect(() => () => revealTimers.current.forEach(clearTimeout), []);
  const revealAll = () => {
    const queue = puzzle.parties
      .map((party) => party.partyId)
      .filter((partyId) => !revealed.has(partyId));
    revealTimers.current = queue.map((partyId, i) =>
      setTimeout(
        () => reveal(partyId),
        reduceMotion ? 0 : i * REVEAL_ALL_STEP_MS,
      ),
    );
  };

  if (phase === 'briefing') {
    return (
      <div className="py-6">
        <Briefing
          number={number}
          playDate={today}
          puzzle={puzzle}
          onStart={() => {
            setStarted(true);
            goTop();
          }}
        />
      </div>
    );
  }

  if (phase === 'result') {
    return (
      <div className="py-6">
        <Result
          number={number}
          playDate={today}
          puzzle={puzzle}
          stamping={!stamped.current}
          onReview={() => {
            setShowResult(false);
            goTop();
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 py-6">
      <Hemicycle
        parties={puzzle.parties}
        unaffiliated={puzzle.unaffiliated}
        states={chamberStates(puzzle, phase, game.guesses, revealed)}
        center={chamberCenter(puzzle, phase, game.guesses, revealed)}
        onPartyClick={phase === 'reveal' ? reveal : undefined}
      />
      {phase === 'reveal' && (
        <ChamberLegend
          kind={revealed.size > 0 ? 'votes' : 'guess'}
          unaffiliated={puzzle.unaffiliated}
        />
      )}
      <div
        key={phase}
        className="animate-stimmts-screen motion-reduce:animate-none"
      >
        {phase === 'answering' ? (
          <GuessStep puzzle={puzzle} guesses={game.guesses} today={today} />
        ) : (
          <Reveal
            puzzle={puzzle}
            guesses={game.guesses}
            revealed={revealed}
            onReveal={reveal}
            onRevealAll={revealAll}
            onShowResult={() => {
              setShowResult(true);
              goTop();
            }}
          />
        )}
      </div>
    </div>
  );
}

export default PuzzleGame;
