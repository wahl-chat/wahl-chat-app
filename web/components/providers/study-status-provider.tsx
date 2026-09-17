'use client';

import { listenToStudyStatus } from '@/lib/firebase/firebase';
import {
  type ReactNode,
  createContext,
  useContext,
  useEffect,
  useState,
} from 'react';

/**
 * One app-wide subscription to the PledgeTracker kill switch
 * (system_status/pledge_study).
 *
 * It lives here rather than in ChatStudyWrapper because surfaces outside the
 * chat have to know too: while the study runs, no other survey may compete
 * with the study questionnaire, and those surfaces (the newsletter ask, the
 * Wahl-Swiper feedback card) are mounted well outside the chat store.
 *
 * `undefined` means "not known yet" and is NOT the same as `false`. The gate
 * hides PledgeTracker while the state is unknown, so that a user who turns out
 * to be in the control group never sees a flash of the feature. Collapsing the
 * two would reintroduce exactly that exposure.
 */
const StudyStatusContext = createContext<boolean | undefined>(undefined);

/** `true` while the study is on, `false` while off, `undefined` until known. */
export function useStudyRunning(): boolean | undefined {
  return useContext(StudyStatusContext);
}

export function StudyStatusProvider({ children }: { children: ReactNode }) {
  const [running, setRunning] = useState<boolean | undefined>(undefined);

  useEffect(
    () => listenToStudyStatus(({ enabled }) => setRunning(enabled)),
    [],
  );

  return (
    <StudyStatusContext.Provider value={running}>
      {children}
    </StudyStatusContext.Provider>
  );
}

export default StudyStatusProvider;
