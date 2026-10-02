'use client';

import { sortBySeating } from '@/lib/daily/seating-order';
import type { DigestPartyPosition } from '@/lib/firebase/firebase.types';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import Image from 'next/image';
import { useState } from 'react';
import { MUTED_TEXT } from './card-styles';

/**
 * Party logo on the party's own background colour, as on the rest of the
 * site: the logo files are transparent and often white-lettered (the AfD's is
 * white on nothing), so they only read on their brand colour. A missing logo
 * leaves the plain colour tile.
 */
export function PartyMark({
  partyId,
  color,
  className,
}: {
  partyId: string;
  color: string;
  className?: string;
}) {
  const [missing, setMissing] = useState(false);
  return (
    <span
      className={cn(
        'flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-[4px] border-2 border-[var(--daily-ink)] p-1',
        className,
      )}
      style={{ backgroundColor: color }}
    >
      {!missing && (
        <Image
          src={buildPartyImageUrl(partyId)}
          alt=""
          width={28}
          height={28}
          className="size-full object-contain"
          onError={() => setMissing(true)}
        />
      )}
    </span>
  );
}

/** One bullet per Fraktion: logo, party, its speakers, its position. */
export function PartyPositions({
  positions,
}: {
  positions: DigestPartyPosition[];
}) {
  return (
    <ul className="flex flex-col gap-3">
      {sortBySeating(positions).map((position) => (
        <li
          key={position.party_id}
          className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3"
        >
          <PartyMark partyId={position.party_id} color={position.color} />
          <div className="flex flex-col gap-0.5">
            <p className="text-sm leading-snug">
              <span className="font-bold">{position.party_name}</span>
              {position.speakers.length > 0 && (
                <span className={cn('text-xs', MUTED_TEXT)}>
                  {' · '}
                  {position.speakers.map((speaker, i) => (
                    <span key={speaker.name}>
                      {i > 0 && ', '}
                      {speaker.url ? (
                        <a
                          href={speaker.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="underline decoration-1 underline-offset-2 hover:decoration-2"
                        >
                          {speaker.name}
                        </a>
                      ) : (
                        speaker.name
                      )}
                    </span>
                  ))}
                </span>
              )}
            </p>
            <p className="text-[15px] leading-relaxed">{position.position}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
