'use client';

import { sortBySeating } from '@/lib/daily/seating-order';
import type { DigestPartyPosition } from '@/lib/firebase/firebase.types';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import Image from 'next/image';
import { useState } from 'react';

/**
 * Party logo on the party's own background colour, as everywhere on the site:
 * the logo files are transparent and often white-lettered, so they only read
 * on their brand colour. Falls back to the name when there is no logo.
 */
export function PartyLogo({
  partyId,
  name,
  color,
  className,
}: {
  partyId: string;
  name: string;
  color: string;
  className?: string;
}) {
  const [missing, setMissing] = useState(false);
  return (
    <span
      className={cn(
        'flex h-8 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md px-1',
        className,
      )}
      style={{ backgroundColor: color }}
    >
      {missing ? (
        <span className="truncate text-[11px] font-bold text-white">
          {name}
        </span>
      ) : (
        <Image
          src={buildPartyImageUrl(partyId)}
          alt={name}
          width={52}
          height={28}
          className="h-6 w-full object-contain"
          onError={() => setMissing(true)}
        />
      )}
    </span>
  );
}

/** The Fraktion that brought the debate first, then everyone else in
 * seating order. */
function ordered(
  positions: DigestPartyPosition[],
  openedBy: string | null | undefined,
): DigestPartyPosition[] {
  const seated = sortBySeating(positions);
  const opener = seated.find((p) => p.party_id === openedBy);
  return opener ? [opener, ...seated.filter((p) => p !== opener)] : seated;
}

/** "Wer sagt was": one line per Fraktion, marked by its logo. */
export function PartyPositions({
  positions,
  openedBy,
  limit,
  clamp = false,
}: {
  positions: DigestPartyPosition[];
  openedBy?: string | null;
  limit?: number;
  /** Cards show the gist; the detail view shows each position in full. */
  clamp?: boolean;
}) {
  return (
    <dl className="divide-y divide-[var(--daily-border)] border-t border-[var(--daily-border)]">
      {ordered(positions, openedBy)
        .slice(0, limit)
        .map((position) => (
          <div
            key={position.party_id}
            className="flex items-start gap-3 py-3 text-[15px] leading-snug"
          >
            <dt>
              <PartyLogo
                partyId={position.party_id}
                name={position.party_name}
                color={position.color}
              />
            </dt>
            <dd className={cn('min-w-0 pt-1', clamp && 'line-clamp-2')}>
              {position.position}
            </dd>
          </div>
        ))}
    </dl>
  );
}
