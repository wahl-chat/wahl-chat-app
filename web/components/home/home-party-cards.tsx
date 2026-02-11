'use client';

import PartyCards from '@/components/party-cards';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { track } from '@vercel/analytics/react';

type Props = {
  contextId?: string;
};

export default function HomePartyCards({
  contextId = DEFAULT_CONTEXT_ID,
}: Props) {
  const handlePartyClick = (partyId: string) => {
    track('home_page_party_clicked', {
      party: partyId,
      context: contextId,
    });
  };

  return (
    <PartyCards
      className="mt-1"
      selectable={false}
      onPartyClicked={handlePartyClick}
      contextId={contextId}
    />
  );
}
