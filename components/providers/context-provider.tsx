'use client';

import type { Context } from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import { createContext, useContext, useMemo } from 'react';

type ContextProviderValue = {
  context: Context;
  contexts: Context[];
  parties?: PartyDetails[];
  partyCount: number;
};

const ElectionContext = createContext<ContextProviderValue | undefined>(
  undefined,
);

export type ContextProviderProps = {
  children: React.ReactNode;
  context: Context;
  contexts: Context[];
  parties?: PartyDetails[];
};

export function ContextProvider({
  children,
  context,
  contexts,
  parties,
}: ContextProviderProps) {
  const value = useMemo(
    () => ({
      context,
      contexts,
      parties,
      partyCount: parties?.length ?? 0,
    }),
    [context, contexts, parties],
  );

  return (
    <ElectionContext.Provider value={value}>
      {children}
    </ElectionContext.Provider>
  );
}

export function useElectionContext(options: {
  optional: true;
}): ContextProviderValue | undefined;
export function useElectionContext(options?: {
  optional?: false;
}): ContextProviderValue;
export function useElectionContext(options?: { optional?: boolean }) {
  const context = useContext(ElectionContext);
  if (!context && !options?.optional) {
    throw new Error('useElectionContext must be used within a ContextProvider');
  }
  return context;
}

export function useCurrentContext(options: { optional: true }):
  | Context
  | undefined;
export function useCurrentContext(options?: { optional?: false }): Context;
export function useCurrentContext(options?: { optional?: boolean }) {
  const electionContext = useElectionContext(options as { optional: true });
  return electionContext?.context;
}

export function useContexts() {
  return useElectionContext().contexts;
}

export function useContextParties(partyIds?: string[]) {
  const { parties } = useElectionContext();

  return useMemo(() => {
    if (partyIds) {
      return parties?.filter((p) => partyIds.includes(p.party_id));
    }
    return parties;
  }, [parties, partyIds]);
}

export function useContextParty(partyId: string) {
  const parties = useContextParties([partyId]);
  return parties?.[0];
}
