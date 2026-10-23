'use client';

import { getGame } from '@/lib/stimmts/progress';
import type { Puzzle } from '@/lib/stimmts/types';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useState } from 'react';
import Briefing from './briefing';
import GuessStep from './guess-step';
import Reveal from './reveal';

type Props = {
  number: number;
  puzzle: Puzzle;
  /** Today's Berlin date: the puzzle's day, and the day answers are saved on. */
  today: string;
};

/**
 * One puzzle from briefing to result. Which screen shows is derived from the
 * saved answers, so reloading the page resumes exactly where the player was.
 */
function PuzzleGame({ number, puzzle, today }: Props) {
  const game = useProgress((state) => getGame(state.progress, puzzle.id));
  const [started, setStarted] = useState(false);
  // A game that was already finished when the page opened shows its result
  // straight away instead of replaying the reveal.
  const [alreadyFinished] = useState(game.finishedOn !== null);

  const finished = game.finishedOn !== null;
  const hasAnswers = Object.keys(game.guesses).length > 0;

  if (!finished && !started && !hasAnswers) {
    return (
      <div className="py-6">
        <Briefing
          number={number}
          playDate={today}
          puzzle={puzzle}
          onStart={() => setStarted(true)}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 py-6">
      <header>
        <p className="text-sm text-muted-foreground">
          Stimmt&apos;s? #{number} · {puzzle.topic}
        </p>
        {/* German compounds ("Gebäudemodernisierungsgesetz") are wider than a
            phone screen, so the title may break inside a word. */}
        <h1 className="hyphens-auto break-words text-2xl font-bold">
          {puzzle.title}
        </h1>
      </header>

      {finished ? (
        <Reveal
          number={number}
          puzzle={puzzle}
          guesses={game.guesses}
          startRevealed={alreadyFinished}
        />
      ) : (
        <GuessStep puzzle={puzzle} guesses={game.guesses} today={today} />
      )}
    </div>
  );
}

export default PuzzleGame;
