'use client';

import {
  type LandingComposerAction,
  type LandingComposerState,
  landingComposerReducer,
} from '@/lib/landing-composer-state';
import { type Dispatch, createContext, useContext, useReducer } from 'react';

const LandingComposerContext = createContext<{
  state: LandingComposerState;
  dispatch: Dispatch<LandingComposerAction>;
} | null>(null);

export function LandingComposerProvider({
  initialContextId,
  children,
}: {
  initialContextId: string;
  children: React.ReactNode;
}) {
  const [state, dispatch] = useReducer(landingComposerReducer, {
    contextId: initialContextId,
    question: '',
    partyIds: [],
    focusRequest: 0,
  });

  return (
    <LandingComposerContext.Provider value={{ state, dispatch }}>
      {children}
    </LandingComposerContext.Provider>
  );
}

export function useLandingComposer() {
  const composer = useContext(LandingComposerContext);
  if (!composer) throw new Error('Landing composer provider is missing');
  return composer;
}
