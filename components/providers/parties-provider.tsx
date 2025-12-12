'use client';
import type { PartyDetails } from '@/lib/party-details';
import {} from '@/lib/utils';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

type PartiesContextType = {
  parties?: PartyDetails[];
  partyCount: number;
};

export const PartiesContext = createContext<PartiesContextType | undefined>(
  undefined,
);

export type Props = {
  children: React.ReactNode;
  parties: PartyDetails[];
};

export const useParties = (partyIds?: string[]) => {
  const context = useContext(PartiesContext);
  if (!context) {
    throw new Error('useParties must be used within a PartiesProvider');
  }

  const parties = useMemo(() => {
    if (partyIds) {
      return context.parties?.filter((p) => partyIds.includes(p.party_id));
    }
    return context.parties;
  }, [context.parties, partyIds]);

  return parties;
};

export const useParty = (partyId: string) => {
  const parties = useParties([partyId]);

  if (!parties) {
    return undefined;
  }

  return parties[0];
};

export const PartiesProvider = ({ children, parties }: Props) => {
  const [randomizedParties, setRandomizedParties] = useState<
    PartyDetails[] | undefined
  >();

  useEffect(() => {
    setRandomizedParties([...parties].sort(() => Math.random() - 0.5));
  }, [parties]);

  return (
    <PartiesContext.Provider
      value={{ parties: randomizedParties, partyCount: parties?.length }}
    >
      {children}
    </PartiesContext.Provider>
  );
};
