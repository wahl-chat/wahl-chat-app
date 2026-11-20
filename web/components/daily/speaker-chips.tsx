'use client';

import type { DigestSpeaker } from '@/lib/firebase/firebase.types';
import { cn, formatTimestamp } from '@/lib/utils';
import { PlayIcon, UserRoundIcon } from 'lucide-react';
import Image from 'next/image';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';
import { GlossaryLabel } from './glossary-text';

/** One chip per speaker of a Fraktion: who spoke, and for how long. A tap
 * opens what the Bundestag publishes about them. A member of the government
 * carries the office they spoke in inside the chip: they speak for the
 * government, and the reader should not take it for the Fraktion's line. */
export function SpeakerChips({
  speakers,
  photos = {},
  onOpen,
}: {
  speakers: DigestSpeaker[];
  /** The official portrait by MdB ID, once the records have loaded. */
  photos?: Record<string, string>;
  onOpen: (speaker: DigestSpeaker) => void;
}) {
  const photoOf = (speaker: DigestSpeaker) =>
    speaker.mdb_id ? photos[speaker.mdb_id] : undefined;
  return (
    <div
      role="group"
      aria-label="Redner·innen"
      className="flex flex-wrap gap-1.5"
    >
      {speakers.map((speaker) =>
        speaker.role ? (
          <div
            key={speaker.name}
            className={cn('relative flex max-w-full flex-col pr-3', CHIP)}
          >
            <SpeakerButton
              speaker={speaker}
              photo={photoOf(speaker)}
              onOpen={onOpen}
              className={STRETCHED}
            />
            <span
              className={cn(
                'max-w-64 pb-0.5 pl-9 text-[11px] leading-snug',
                MUTED_TEXT,
              )}
            >
              <GlossaryLabel label={speaker.role} />
            </span>
          </div>
        ) : (
          <SpeakerButton
            key={speaker.name}
            speaker={speaker}
            photo={photoOf(speaker)}
            onOpen={onOpen}
            className={cn(FOCUS_RING, 'min-h-9 pr-3', CHIP)}
          />
        ),
      )}
    </div>
  );
}

const CHIP =
  'rounded-[18px] bg-[var(--daily-surface)] py-1 pl-1 transition-colors hover:bg-[var(--daily-border)]';

/** The name row's button stretched over the whole chip, office included, so
 * a tap anywhere opens the record; the office's glossary terms sit above it. */
const STRETCHED =
  "text-left after:absolute after:inset-0 after:rounded-[18px] after:content-[''] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-[var(--daily-ink)] focus-visible:after:ring-offset-2 focus-visible:after:ring-offset-[var(--daily-canvas)]";

function SpeakerButton({
  speaker,
  photo,
  onOpen,
  className,
}: {
  speaker: DigestSpeaker;
  photo: string | undefined;
  onOpen: (speaker: DigestSpeaker) => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen(speaker)}
      aria-label={
        speaker.duration
          ? `${speaker.name}, Rede ${formatTimestamp(speaker.duration)} Minuten – Profil öffnen`
          : `${speaker.name} – Profil öffnen`
      }
      className={cn(
        'inline-flex items-center gap-2 whitespace-nowrap text-[13px] font-semibold',
        className,
      )}
    >
      <span
        aria-hidden
        className="flex size-7 shrink-0 items-center justify-center overflow-hidden rounded-full bg-[var(--daily-canvas)] text-[var(--daily-muted)]"
      >
        {photo ? (
          // Served by bundestag.de as published, like on the card.
          <Image
            src={photo}
            alt=""
            width={28}
            height={28}
            unoptimized
            loading="lazy"
            decoding="async"
            className="size-7 object-cover object-top"
          />
        ) : (
          <UserRoundIcon className="size-3.5" />
        )}
      </span>
      {speaker.name}
      {speaker.duration ? (
        <span
          aria-hidden
          className="inline-flex items-center gap-0.5 text-[11px] font-medium text-[var(--daily-muted)]"
        >
          <PlayIcon className="size-2.5 fill-current" />
          {formatTimestamp(speaker.duration)}
        </span>
      ) : null}
    </button>
  );
}
