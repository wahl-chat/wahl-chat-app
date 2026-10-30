'use client';

import {
  type Phase,
  chamberCenter,
  chamberStates,
  selectParty,
} from '@/lib/stimmts/game-view';
import { getGame } from '@/lib/stimmts/progress';
import type { Puzzle, Schedule } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useReducedMotion } from 'motion/react';
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
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
  schedule: Schedule;
  /** Today's Berlin date: the puzzle's day, and the day answers are saved on. */
  today: string;
  onOpenDay: (number: number) => void;
  canOpenDay: (number: number) => boolean;
};

/**
 * One puzzle from briefing to result. Which screen shows is derived from the
 * saved answers, so reloading the page resumes exactly where the player was.
 * The chamber is the board: it stays on top while the player answers and
 * while the parties are turned over.
 */
function PuzzleGame({
  number,
  puzzle,
  schedule,
  today,
  onOpenDay,
  canOpenDay,
}: Props) {
  const game = useProgress((state) => getGame(state.progress, puzzle.id));
  const reduceMotion = useReducedMotion() ?? false;
  const [started, setStarted] = useState(false);
  // A game that was already finished when the page opened shows its result
  // straight away instead of replaying the reveal.
  const [alreadyFinished] = useState(game.finishedOn !== null);
  const [showResult, setShowResult] = useState(alreadyFinished);
  // Opened from the result's outcome card: the vote itself, without tips.
  const [votesOnly, setVotesOnly] = useState(false);
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
  }, [showResult]);

  const finished = game.finishedOn !== null;
  const hasAnswers = Object.keys(game.guesses).length > 0;

  // Finished in another tab while this one was open: the player saw the
  // reveal there, so this tab goes straight to the result too (before the
  // next paint, so the reveal never flashes up).
  const finishedHere = useProgress((state) =>
    state.finishedHere.includes(puzzle.id),
  );
  const finishedElsewhere = finished && !finishedHere && !alreadyFinished;
  useLayoutEffect(() => {
    if (finishedElsewhere) {
      stamped.current = true;
      setRevealed(new Set(puzzle.parties.map((party) => party.partyId)));
      setShowResult(true);
    }
  }, [finishedElsewhere, puzzle]);
  const phase: Phase = finished
    ? showResult
      ? 'result'
      : 'reveal'
    : started || hasAnswers
      ? 'answering'
      : 'briefing';

  // Every screen but the briefing (whose Stimmkarte is the heading) opens on
  // a heading for screen readers, and the focus moves to it when the screen
  // changes; otherwise it would stay on a button that is gone.
  const screenHeading = useRef<HTMLHeadingElement>(null);
  const lastPhase = useRef(phase);
  useEffect(() => {
    if (phase !== lastPhase.current) {
      lastPhase.current = phase;
      screenHeading.current?.focus({ preventScroll: true });
    }
  }, [phase]);
  const heading = (text: string) => (
    <h1 ref={screenHeading} tabIndex={-1} className="sr-only">
      Stimmt’s? Nr. {number}: {text}
    </h1>
  );

  const goTop = useCallback(() => {
    window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
  }, [reduceMotion]);

  const reveal = useCallback((partyId: string) => {
    setRevealed((previous) => new Set(previous).add(partyId));
  }, []);

  // The party whose counts are open under its row in "Deine Tipps".
  const [openParty, setOpenParty] = useState<string | null>(null);
  const select = (partyId: string) => {
    const next = selectParty({ revealed, open: openParty }, partyId);
    setRevealed(next.revealed);
    setOpenParty(next.open);
  };

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
        {heading('Dein Ergebnis')}
        <Result
          number={number}
          playDate={today}
          puzzle={puzzle}
          schedule={schedule}
          stamping={!stamped.current}
          onOpenDay={onOpenDay}
          canOpenDay={canOpenDay}
          onReview={() => {
            setRevealed(new Set(puzzle.parties.map((party) => party.partyId)));
            setOpenParty(null);
            setVotesOnly(true);
            setShowResult(false);
            goTop();
          }}
        />
      </div>
    );
  }

  const tips = votesOnly ? {} : game.guesses;

  return (
    <div className="flex flex-col gap-4 py-6">
      {heading(
        phase === 'answering'
          ? 'Tipps abgeben'
          : votesOnly
            ? 'So wurde abgestimmt'
            : 'Auflösung',
      )}
      <Hemicycle
        parties={puzzle.parties}
        unaffiliated={puzzle.unaffiliated}
        states={chamberStates(puzzle, phase, tips, revealed)}
        center={chamberCenter(puzzle, phase, tips, revealed)}
        onPartyClick={phase === 'reveal' ? select : undefined}
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
            guesses={tips}
            revealed={revealed}
            open={openParty}
            onSelect={select}
            onRevealAll={revealAll}
            onShowResult={() => {
              setShowResult(true);
              setVotesOnly(false);
              goTop();
            }}
          />
        )}
      </div>
    </div>
  );
}

export default PuzzleGame;
