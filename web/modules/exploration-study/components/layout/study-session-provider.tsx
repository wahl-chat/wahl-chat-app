'use client';

import type { StudySession } from '@/modules/exploration-study/types';
import { type ReactNode, createContext, useContext } from 'react';

const StudySessionContext = createContext<StudySession | null>(null);

export function StudySessionProvider({
  session,
  children,
}: {
  session: StudySession;
  children: ReactNode;
}) {
  return (
    <StudySessionContext.Provider value={session}>
      {children}
    </StudySessionContext.Provider>
  );
}

export function useStudySessionContext(): StudySession {
  const session = useContext(StudySessionContext);
  if (!session) {
    throw new Error(
      'useStudySessionContext must be used inside <StudySessionProvider>',
    );
  }
  return session;
}
