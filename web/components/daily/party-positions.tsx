'use client';

import { sortBySeating } from '@/lib/daily/seating-order';
import type { NumberedSources } from '@/lib/daily/sources';
import type {
  DigestPartyPosition,
  DigestSpeaker,
  TermRef,
} from '@/lib/firebase/firebase.types';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import Image from 'next/image';
import { Fragment, useState } from 'react';
import { MUTED_TEXT } from './card-styles';
import { GlossaryText } from './glossary-text';
import { SourcePills } from './source-pills';
import { SpeakerChips } from './speaker-chips';

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
export function orderedPositions(
  positions: DigestPartyPosition[],
  openedBy: string | null | undefined,
): DigestPartyPosition[] {
  const seated = sortBySeating(positions);
  const opener = seated.find((p) => p.party_id === openedBy);
  return opener ? [opener, ...seated.filter((p) => p !== opener)] : seated;
}

/** A Fraktion whose position could not be summarised and checked: no
 * sentence is put in its mouth, but its speeches are one click away. */
function SpeechesOnly({ speakers }: { speakers: DigestSpeaker[] }) {
  return (
    <span className={MUTED_TEXT}>
      Reden von{' '}
      {speakers.map((speaker, i) => (
        <Fragment key={speaker.name}>
          {i > 0 && ', '}
          {speaker.url ? (
            <a
              href={speaker.url}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              {speaker.name}
            </a>
          ) : (
            speaker.name
          )}
        </Fragment>
      ))}
    </span>
  );
}

/** "Wer sagt was": one line per Fraktion that spoke, marked by its logo. */
export function PartyPositions({
  positions,
  openedBy,
  limit,
  clamp = false,
  sources,
  onSpeaker,
  speakerPhotos,
  terms,
}: {
  positions: DigestPartyPosition[];
  openedBy?: string | null;
  limit?: number;
  /** Cards show the gist; the detail view shows each position in full. */
  clamp?: boolean;
  /** The detail view cites each position's passages. */
  sources?: NumberedSources;
  /** The detail view lists each Fraktion's speakers, each opening what the
   * Bundestag publishes about them. */
  onSpeaker?: (speaker: DigestSpeaker, party: DigestPartyPosition) => void;
  /** The speakers' official portraits by MdB ID. */
  speakerPhotos?: Record<string, string>;
  /** The item's expert terms the glossary explains. */
  terms?: TermRef[];
}) {
  return (
    <dl className="divide-y divide-[var(--daily-border)] border-t border-[var(--daily-border)]">
      {orderedPositions(positions, openedBy)
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
            <dd
              className={cn(
                'min-w-0 pt-1',
                clamp ? 'line-clamp-2' : 'flex flex-col gap-2',
              )}
            >
              {position.position ? (
                <span>
                  <GlossaryText text={position.position} terms={terms} />
                  {sources && (
                    <SourcePills
                      numbers={sources.position(position.party_id)}
                      sources={sources}
                    />
                  )}
                </span>
              ) : onSpeaker ? null : (
                <SpeechesOnly speakers={position.speakers} />
              )}
              {onSpeaker && position.speakers.length > 0 && (
                <SpeakerChips
                  speakers={position.speakers}
                  photos={speakerPhotos}
                  onOpen={(speaker) => onSpeaker(speaker, position)}
                />
              )}
            </dd>
          </div>
        ))}
    </dl>
  );
}
