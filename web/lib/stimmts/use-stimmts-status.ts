import { listenToStimmtsStatus } from '@/lib/firebase/firebase';
import { useCallback, useEffect, useState } from 'react';
import { type StatusState, parseStimmtsStatus } from './status';

// A blocked or offline connection never answers at all, so after this long
// the page stops waiting and offers to try again.
const STATUS_TIMEOUT_MS = 8000;

/**
 * Follows the switch live, so turning the game on or off reaches open pages
 * at once. Once the status is known it stays known: a dropped connection
 * later on does not take away a game that is being played.
 */
export function useStimmtsStatus(): { state: StatusState; retry: () => void } {
  const [state, setState] = useState<StatusState>({ kind: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setState({ kind: 'loading' });
    const giveUp = () =>
      setState((current) =>
        current.kind === 'known' ? current : { kind: 'unreachable' },
      );
    const timer = setTimeout(giveUp, STATUS_TIMEOUT_MS);
    const unsubscribe = listenToStimmtsStatus((data, fromCache) => {
      // Offline, Firestore reports a doc it has never seen as missing, which
      // would read as "switched off". Only the server can say that.
      if (fromCache && data === undefined) {
        return;
      }
      clearTimeout(timer);
      setState({ kind: 'known', status: parseStimmtsStatus(data) });
    }, giveUp);
    return () => {
      clearTimeout(timer);
      unsubscribe();
    };
  }, [attempt]);

  const retry = useCallback(() => setAttempt((count) => count + 1), []);
  return { state, retry };
}
