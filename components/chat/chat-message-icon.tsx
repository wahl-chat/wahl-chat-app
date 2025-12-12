'use client';

import { useParty } from '@/components/providers/parties-provider';
import { WAHL_CHAT_PARTY_ID } from '@/lib/constants';
import type { PartyDetails } from '@/lib/party-details';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import { SparklesIcon } from 'lucide-react';
import Image from 'next/image';
import Logo from './logo';

type Props = {
  partyId?: string;
  party?: PartyDetails;
};

export function ChatMessageIcon({ partyId, party }: Props) {
  const clientParty = useParty(partyId ?? '');

  const normalizedParty = clientParty ?? party;

  return (
    <div
      style={{ backgroundColor: normalizedParty?.background_color }}
      className={cn(
        'relative flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-full ring-1 ring-border',
        party && 'dark:bg-slate-200',
      )}
    >
      {normalizedParty ? (
        <Image
          src={buildPartyImageUrl(normalizedParty?.party_id ?? '')}
          alt={normalizedParty?.name ?? 'Keine Partei ausgewählt'}
          fill
          sizes="32px"
          className="object-contain"
        />
      ) : partyId === WAHL_CHAT_PARTY_ID ? (
        <Logo variant="small" className="size-8 p-2" />
      ) : (
        <SparklesIcon className="size-4" />
      )}
    </div>
  );
}
