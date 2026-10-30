'use client';

import { Button } from '@/components/ui/button';
import {
  addDays,
  berlinDate,
  daysBetween,
  nextPuzzleAt,
} from '@/lib/stimmts/berlin-time';
import { PUZZLES, SCHEDULE } from '@/lib/stimmts/content';
import { formatDate } from '@/lib/stimmts/labels';
import {
  type Clock,
  isPreviewEnabled,
  resolveClock,
} from '@/lib/stimmts/preview';
import { getGame } from '@/lib/stimmts/progress';
import { STORAGE_KEY } from '@/lib/stimmts/progress-store';
import { getTodaysPuzzle, puzzleForDay } from '@/lib/stimmts/schedule';
import { useProgress } from '@/lib/stimmts/use-progress';
import { useCallback, useEffect, useState } from 'react';
import PastPuzzle from './past-puzzle';
import PuzzleGame from './puzzle-game';

function Message({ children }: { children: React.ReactNode }) {
  return <p className="py-10 text-center text-muted-foreground">{children}</p>;
}

function PreviewBar({
  clock,
  puzzleId,
}: {
  clock: Clock;
  puzzleId?: string;
}) {
  const resetGame = useProgress((state) => state.resetGame);
  const day = daysBetween(SCHEDULE.startDate, berlinDate(clock.now)) + 1;

  // Replays this puzzle and keeps the other days, so the Wahlperiode across
  // several days can be tested without starting over.
  const resetPuzzle = () => {
    if (puzzleId) {
      resetGame(puzzleId);
    }
    window.location.reload();
  };
  const resetEverything = () => {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Nothing saved, nothing to reset.
    }
    window.location.reload();
  };

  return (
    <div className="mt-6 flex flex-col gap-2 rounded-md border border-dashed p-3 text-xs text-muted-foreground">
      <span>
        Vorschau-Modus · Tag {day} · mit ?day=N einen anderen Tag öffnen
      </span>
      <div className="flex flex-wrap gap-2">
        {puzzleId && (
          <Button size="sm" variant="outline" onClick={resetPuzzle}>
            Dieses Rätsel zurücksetzen
          </Button>
        )}
        <Button size="sm" variant="outline" onClick={resetEverything}>
          Alles zurücksetzen
        </Button>
      </div>
    </div>
  );
}

function StimmtsGame() {
  const hydrate = useProgress((state) => state.hydrate);
  const hydrated = useProgress((state) => state.hydrated);
  const refresh = useProgress((state) => state.refresh);
  const progress = useProgress((state) => state.progress);
  const [clock, setClock] = useState<Clock | null>(null);
  // A past day of the Wahlperiode the player is looking at, if any.
  const [pastDay, setPastDay] = useState<number | null>(null);

  const refreshClock = useCallback(() => {
    setClock(
      resolveClock({
        previewEnabled: isPreviewEnabled(),
        search: window.location.search,
        schedule: SCHEDULE,
        now: new Date(),
      }),
    );
  }, []);

  // Everything that depends on the player's browser (saved progress, the time,
  // the address) is read after mount, so the server's first render and the
  // browser's first render are identical.
  useEffect(() => {
    hydrate();
    refreshClock();
  }, [hydrate, refreshClock]);

  // The page may be an older copy: a tab left open, or one the browser
  // restores on "back". Whenever it comes back into view it catches up with
  // what was played since, so it never shows (or accepts) stale answers.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        refresh();
      }
    };
    window.addEventListener('pageshow', refresh);
    window.addEventListener('focus', refresh);
    window.addEventListener('storage', refresh);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('pageshow', refresh);
      window.removeEventListener('focus', refresh);
      window.removeEventListener('storage', refresh);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [refresh]);

  // A page left open past Berlin midnight switches to the new day's puzzle by
  // itself. The extra second keeps the timer from firing just before the day
  // changes. A sleeping device fires it late, on waking, which is just as good.
  useEffect(() => {
    if (!clock) {
      return;
    }
    const wait = nextPuzzleAt(new Date()).getTime() - Date.now();
    const timer = setTimeout(refreshClock, wait + 1000);
    return () => clearTimeout(timer);
  }, [clock, refreshClock]);

  if (!clock || !hydrated) {
    return <Message>Lädt …</Message>;
  }

  const today = getTodaysPuzzle({
    schedule: SCHEDULE,
    puzzles: PUZZLES,
    now: clock.now,
  });
  const dayPuzzle = (number: number) =>
    puzzleForDay({
      schedule: SCHEDULE,
      puzzles: PUZZLES,
      number,
    });
  const scrollTop = () => window.scrollTo({ top: 0 });

  const past = pastDay === null ? null : dayPuzzle(pastDay);
  if (pastDay !== null && past) {
    const game = getGame(progress, past.id);
    return (
      <PastPuzzle
        number={pastDay}
        playDate={addDays(SCHEDULE.startDate, pastDay - 1)}
        puzzle={past}
        guesses={game.finishedOn === null ? null : game.guesses}
        onBack={() => {
          setPastDay(null);
          scrollTop();
        }}
      />
    );
  }

  return (
    <>
      {today.status === 'active' && (
        <PuzzleGame
          // A new puzzle must start from its own briefing, not inherit the
          // previous puzzle's "already started" state.
          key={today.puzzle.id}
          number={today.number}
          puzzle={today.puzzle}
          today={berlinDate(clock.now)}
          onOpenDay={(number) => {
            setPastDay(number);
            scrollTop();
          }}
          canOpenDay={(number) => dayPuzzle(number) !== null}
        />
      )}
      {today.status === 'not-started' && (
        <Message>
          Stimmt&apos;s? startet am {formatDate(today.startsOn)}.
        </Message>
      )}
      {today.status === 'finished' && (
        <Message>
          Du hast alle bisherigen Rätsel gespielt. Neue folgen bald.
        </Message>
      )}
      {isPreviewEnabled() && (
        <PreviewBar
          clock={clock}
          puzzleId={today.status === 'active' ? today.puzzle.id : undefined}
        />
      )}
    </>
  );
}

export default StimmtsGame;
