'use client';

import {
  trackPuzzleCompleted,
  trackPuzzleStarted,
} from '@/lib/stimmts/analytics';
import {
  type Phase,
  allRevealed,
  autoResultDelay,
  chamberCenter,
  chamberStates,
  gamePhase,
  selectParty,
} from '@/lib/stimmts/game-view';
import { browserSession, markJustPlayed } from '@/lib/stimmts/presence';
import { getGame } from '@/lib/stimmts/progress';
import { isComplete, scorePuzzle } from '@/lib/stimmts/score';
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
import ChamberLegend from './chamber-legend';
import GuessStep from './guess-step';
import Hemicycle from './hemicycle';
import Result from './result';
import Reveal from './reveal';
import ReviewStep from './review-step';
import ShareBanner from './share-banner';
import StartScreen from './start-screen';

/** "Auflösen" turns the parties over one after another, left to right. */
const REVEAL_ALL_STEP_MS = 450;

type Props = {
  number: number;
  puzzle: Puzzle;
  schedule: Schedule;
  /** Today's Berlin date: the puzzle's day, and the day answers are saved on. */
  today: string;
  /** The challenge from a shared link, shown above the start screen. */
  challenge?: { score: number; text: string } | null;
  /** Server-decided preview mode: shows parts still switched off. */
  preview: boolean;
  onOpenDay: (number: number) => void;
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
  challenge,
  preview,
  onOpenDay,
}: Props) {
  const game = useProgress((state) => getGame(state.progress, puzzle.id));
  const finish = useProgress((state) => state.finish);
  const reduceMotion = useReducedMotion() ?? false;
  const [started, setStarted] = useState(false);
  const startCounted = useRef(false);
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

  // Counted when this page finishes the game, and only then: not again
  // when the page is reloaded or comes back from a past day, and not for a
  // game finished in another tab, which counted it there.
  const countedFinish = useRef(finishedHere);
  useEffect(() => {
    if (finishedHere && !countedFinish.current) {
      countedFinish.current = true;
      trackPuzzleCompleted(number, scorePuzzle(puzzle, game.guesses).correct);
      // The feed flies its card into the header icon on the way back.
      markJustPlayed(today, browserSession(), document.documentElement);
    }
  }, [finishedHere, number, puzzle, game.guesses, today]);
  useLayoutEffect(() => {
    if (finishedElsewhere) {
      stamped.current = true;
      setRevealed(new Set(puzzle.parties.map((party) => party.partyId)));
      setShowResult(true);
    }
  }, [finishedElsewhere, puzzle]);
  const phase: Phase = gamePhase({
    started: started || hasAnswers,
    complete: isComplete(puzzle, game.guesses),
    finished,
    showResult,
  });

  // An answered party asked again from the row of tips. Ends with its next
  // answer: the card then goes on to the first party without a tip, or back
  // to the review when every party has one.
  const [editing, setEditing] = useState<string | null>(null);
  const endEdit = useCallback(() => setEditing(null), []);

  // Every screen but the start screen (whose task is its visible h1) opens on
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
  // The same for the way back from an edit to the review, whose card has
  // replaced the one the focus was on.
  const wasEditing = useRef(false);
  useEffect(() => {
    if (wasEditing.current && editing === null && phase === 'review') {
      screenHeading.current?.focus({ preventScroll: true });
    }
    wasEditing.current = editing !== null;
  }, [editing, phase]);
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
    // Functional, so a tap in the same frame as a sequence timer cannot
    // overwrite the party that timer just turned over.
    setRevealed(
      (previous) =>
        selectParty({ revealed: previous, open: openParty }, partyId).revealed,
    );
    setOpenParty(selectParty({ revealed, open: openParty }, partyId).open);
  };

  const revealTimers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const [revealing, setRevealing] = useState(false);
  useEffect(() => () => revealTimers.current.forEach(clearTimeout), []);
  const revealAll = () => {
    // A second tap must not queue a second sequence beside the first.
    revealTimers.current.forEach(clearTimeout);
    const queue = puzzle.parties
      .map((party) => party.partyId)
      .filter((partyId) => !revealed.has(partyId));
    if (queue.length === 0) {
      return;
    }
    setRevealing(true);
    revealTimers.current = queue.map((partyId, i) =>
      setTimeout(
        () => {
          reveal(partyId);
          if (i === queue.length - 1) {
            setRevealing(false);
          }
        },
        reduceMotion ? 0 : i * REVEAL_ALL_STEP_MS,
      ),
    );
  };

  // "Auflösen" on the review ends the game and starts turning the parties
  // over, so the reveal plays without a second tap.
  const revealFromReview = () => {
    // Only a game this tap finished plays its reveal; one already finished
    // in another tab goes straight to its result instead.
    if (finish(puzzle, today)) {
      revealAll();
    }
  };

  // With tips, the result follows once the last party is turned over, however
  // that happened (the sequence or taps on rows). A vote looked at without
  // tips has no result to move on to; there the player leaves by the button.
  const everyPartyRevealed = allRevealed(puzzle, revealed);
  useEffect(() => {
    if (everyPartyRevealed) {
      setRevealing(false);
    }
  }, [everyPartyRevealed]);
  const showResultNow = useCallback(() => {
    setShowResult(true);
    setVotesOnly(false);
    goTop();
  }, [goTop]);
  useEffect(() => {
    if (phase !== 'reveal' || votesOnly || !everyPartyRevealed) {
      return;
    }
    const timer = setTimeout(showResultNow, autoResultDelay(reduceMotion));
    return () => clearTimeout(timer);
  }, [phase, votesOnly, everyPartyRevealed, reduceMotion, showResultNow]);

  if (phase === 'briefing') {
    return (
      <div className="pb-2 pt-3 md:pt-10">
        <StartScreen
          number={number}
          playDate={today}
          puzzle={puzzle}
          banner={challenge ? <ShareBanner {...challenge} /> : undefined}
          onStart={() => {
            // A double tap lands before the screen is gone; count one start.
            if (startCounted.current) {
              return;
            }
            startCounted.current = true;
            setStarted(true);
            trackPuzzleStarted(number, puzzle.id);
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
          preview={preview}
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
  const asking =
    phase === 'answering' || (phase === 'review' && editing !== null);

  return (
    <div className="flex flex-col gap-4 py-6">
      {heading(
        asking
          ? 'Tipps abgeben'
          : phase === 'review'
            ? 'Deine Tipps'
            : votesOnly
              ? 'So wurde abgestimmt'
              : 'Auflösung',
      )}
      <Hemicycle
        parties={puzzle.parties}
        unaffiliated={puzzle.unaffiliated}
        states={chamberStates(
          puzzle,
          phase,
          tips,
          revealed,
          editing ?? undefined,
        )}
        center={chamberCenter(
          puzzle,
          phase,
          tips,
          revealed,
          editing ?? undefined,
        )}
        onPartyClick={phase === 'reveal' ? select : undefined}
      />
      {phase === 'reveal' && (
        <ChamberLegend
          kind={revealed.size > 0 ? 'votes' : 'guess'}
          unaffiliated={puzzle.unaffiliated}
        />
      )}
      <div
        // An edit from the review swaps the whole card, so it animates in;
        // an edit while answering keeps the card, and the focus on it.
        key={phase === 'review' && editing ? 'edit' : phase}
        className="animate-stimmts-screen motion-reduce:animate-none"
      >
        {asking ? (
          <GuessStep
            puzzle={puzzle}
            guesses={game.guesses}
            today={today}
            editing={editing ?? undefined}
            onEdit={setEditing}
            onAnswered={endEdit}
          />
        ) : phase === 'review' ? (
          <ReviewStep
            puzzle={puzzle}
            guesses={game.guesses}
            onEdit={setEditing}
            onReveal={revealFromReview}
          />
        ) : (
          <Reveal
            puzzle={puzzle}
            guesses={tips}
            revealed={revealed}
            open={openParty}
            onSelect={select}
            onRevealAll={revealAll}
            revealing={revealing}
            onShowResult={votesOnly ? showResultNow : undefined}
          />
        )}
      </div>
    </div>
  );
}

export default PuzzleGame;
