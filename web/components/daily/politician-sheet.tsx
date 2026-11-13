'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogClose,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { useMediaViewer } from '@/components/providers/media-viewer-provider';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import { speakerLogoId, speakerPartyLabel } from '@/lib/daily/party-logos';
import {
  displayName,
  gremienOf,
  mandateLabel,
  officeLines,
  tenureLabel,
} from '@/lib/daily/politicians';
import { speakerViewerSource } from '@/lib/daily/sources';
import {
  getPolitician,
  getSpeakerPhotos,
} from '@/lib/firebase/firebase-server';
import type {
  DigestPartyPosition,
  DigestSpeaker,
  Disclosures,
  Politician,
  RollCallVote,
} from '@/lib/firebase/firebase.types';
import { useIsDesktop } from '@/lib/hooks/use-is-desktop';
import { cn, formatTimestamp } from '@/lib/utils';
import { ChevronDownIcon, PlayIcon, UserRoundIcon, XIcon } from 'lucide-react';
import Image from 'next/image';
import { useEffect, useState } from 'react';
import { FOCUS_RING, MUTED_TEXT, SECTION_LABEL } from './card-styles';
import { GlossaryLabel } from './glossary-text';
import { PartyLogo } from './party-positions';
import { SourceLink } from './vote-panels';

export type OpenSpeaker = {
  speaker: DigestSpeaker;
  party: DigestPartyPosition;
};

/** The official portraits of a debate's speakers, by MdB ID; empty until
 * they load, and for a speaker without one. */
export function useSpeakerPhotos(ids: string[]): Record<string, string> {
  const key = ids.join(',');
  const [loaded, setLoaded] = useState<{
    key: string;
    photos: Record<string, string>;
  } | null>(null);
  useEffect(() => {
    if (!key) {
      return;
    }
    let current = true;
    getSpeakerPhotos(key.split(','))
      .then((photos) => current && setLoaded({ key, photos }))
      .catch(() => current && setLoaded({ key, photos: {} }));
    return () => {
      current = false;
    };
  }, [key]);
  return loaded?.key === key ? loaded.photos : NO_PHOTOS;
}

const NO_PHOTOS: Record<string, string> = {};

// The protocol gives people outside the Bundestag (government, Bundesrat,
// guests) IDs from this range.
const NON_MEMBER_ID = /^999/;

function isNonMember(speaker: DigestSpeaker): boolean {
  return Boolean(speaker.mdb_id && NON_MEMBER_ID.test(speaker.mdb_id));
}

/** One speaker's record, read once their chip is tapped. */
function usePolitician(mdbId: string | null): {
  politician: Politician | null;
  loading: boolean;
} {
  const [loaded, setLoaded] = useState<{
    id: string;
    politician: Politician | null;
  } | null>(null);
  useEffect(() => {
    if (!mdbId) {
      return;
    }
    let current = true;
    getPolitician(mdbId)
      .then((politician) => current && setLoaded({ id: mdbId, politician }))
      .catch(() => current && setLoaded({ id: mdbId, politician: null }));
    return () => {
      current = false;
    };
  }, [mdbId]);
  if (!mdbId) {
    return { politician: null, loading: false };
  }
  return loaded?.id === mdbId
    ? { politician: loaded.politician, loading: false }
    : { politician: null, loading: true };
}

const TILE =
  'flex flex-col gap-0.5 rounded-lg bg-[var(--daily-surface)] px-3 py-2';

function Tile({
  label,
  value,
  wide = false,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  return (
    <div className={cn(TILE, wide && 'col-span-2')}>
      <span className={cn('text-[11px]', MUTED_TEXT)}>{label}</span>
      <span className="text-[13px] font-semibold">{value}</span>
    </div>
  );
}

function Avatar({
  photo,
  party,
  partei,
}: {
  photo: string | undefined;
  party: DigestPartyPosition;
  /** The speaker's own party, once their record has loaded. */
  partei?: string | null;
}) {
  return (
    <div className="relative size-14 shrink-0">
      <div className="flex size-14 items-center justify-center overflow-hidden rounded-full bg-[var(--daily-border)] text-[var(--daily-muted)]">
        {photo ? (
          // Served by bundestag.de as published; not run through the image
          // optimizer, so no copy of it is made here.
          <Image
            src={photo}
            alt=""
            width={56}
            height={56}
            unoptimized
            className="size-14 object-cover object-top"
          />
        ) : (
          <UserRoundIcon className="size-7" aria-hidden />
        )}
      </div>
      <PartyLogo
        partyId={party.party_id}
        logoId={speakerLogoId(party, partei)}
        name={speakerPartyLabel(party, partei)}
        color={party.color}
        className="absolute -bottom-1 -right-3 h-5 w-9 rounded"
      />
    </div>
  );
}

function Committees({ politician }: { politician: Politician }) {
  const rows = gremienOf(politician, 'ausschuss');
  if (rows.length === 0) {
    return null;
  }
  return (
    <section className="flex flex-col">
      <h3 className={cn(SECTION_LABEL, 'pb-1')}>Ausschüsse</h3>
      <ul className="divide-y divide-[var(--daily-border)] border-t border-[var(--daily-border)]">
        {rows.map((row) => (
          <li
            key={row.gremium}
            className="flex min-h-10 items-center justify-between gap-3 py-1.5 text-[14px]"
          >
            <span>{row.gremium}</span>
            <span
              className={cn(
                'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold',
                row.level === 'deputy'
                  ? 'bg-[var(--daily-surface)] text-[var(--daily-muted)]'
                  : 'bg-[var(--daily-ink)] text-[var(--daily-canvas)]',
              )}
            >
              <GlossaryLabel label={row.role} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function OtherGremien({ politician }: { politician: Politician }) {
  const rows = gremienOf(politician, 'sonstige');
  if (rows.length === 0) {
    return null;
  }
  return (
    <section className="flex flex-col gap-1.5">
      <h3 className={SECTION_LABEL}>Weitere Gremien &amp; Ämter</h3>
      <ul className="flex flex-wrap gap-1.5">
        {rows.map((row) => (
          <li
            key={row.gremium}
            className="rounded-2xl border border-[var(--daily-border)] px-2.5 py-1 text-[13px]"
          >
            {row.gremium}
            <span className={MUTED_TEXT}>
              {' · '}
              <GlossaryLabel label={row.role} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** A section that stays folded until asked for: long lists the card should
 * not open with. */
function FoldedSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} asChild>
      <section className="flex flex-col gap-1.5">
        <CollapsibleTrigger
          className={cn(
            FOCUS_RING,
            'flex min-h-10 items-center justify-between gap-2 rounded-md text-left',
          )}
        >
          <h3 className={SECTION_LABEL}>{title}</h3>
          <ChevronDownIcon
            aria-hidden
            className={cn(
              'size-4 text-[var(--daily-muted)] transition-transform',
              open && 'rotate-180',
            )}
          />
        </CollapsibleTrigger>
        <CollapsibleContent className="flex flex-col gap-3 text-[13px] leading-snug">
          {children}
        </CollapsibleContent>
      </section>
    </Collapsible>
  );
}

const VOTE_BADGE: Record<RollCallVote['vote'], string> = {
  yes: 'bg-[var(--daily-yes-bg)] text-[var(--daily-yes)]',
  no: 'bg-[var(--daily-no-bg)] text-[var(--daily-no)]',
  abstain: 'bg-[var(--daily-surface)] text-[var(--daily-ink)]',
  absent: 'bg-[var(--daily-surface)] text-[var(--daily-muted)]',
  other: 'bg-[var(--daily-surface)] text-[var(--daily-muted)]',
};

const voteDayFormat = new Intl.DateTimeFormat('de-DE', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: 'UTC',
});

/** The latest namentliche Abstimmungen as the profile lists them, each
 * linked to the vote's own page with every member's vote. */
function RollCallList({
  votes,
  bioUrl,
}: {
  votes: RollCallVote[];
  bioUrl: string | null;
}) {
  return (
    <FoldedSection title="Aktuelle namentliche Abstimmungen">
      <ul className="divide-y divide-[var(--daily-border)] border-t border-[var(--daily-border)]">
        {votes.map((vote) => (
          <li
            key={`${vote.day}-${vote.url ?? vote.title}`}
            className="flex items-center justify-between gap-3 py-2"
          >
            <span className="flex min-w-0 flex-col">
              <span className={cn('text-[11px]', MUTED_TEXT)}>
                {voteDayFormat.format(new Date(`${vote.day}T00:00:00Z`))}
              </span>
              {vote.url ? (
                <a
                  href={vote.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(
                    FOCUS_RING,
                    'rounded-sm text-[14px] underline-offset-2 hover:underline',
                  )}
                >
                  {vote.title}
                </a>
              ) : (
                <span className="text-[14px]">{vote.title}</span>
              )}
            </span>
            <span
              className={cn(
                'shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold',
                VOTE_BADGE[vote.vote],
              )}
            >
              {vote.label}
            </span>
          </li>
        ))}
      </ul>
      {bioUrl && (
        <SourceLink href={`${bioUrl}?subview=na`}>
          Alle Abstimmungen auf bundestag.de
        </SourceLink>
      )}
    </FoldedSection>
  );
}

/** The Veröffentlichungspflichtige Angaben exactly as listed on the
 * profile: one block per organisation, its functions below it. */
function DisclosureList({ disclosures }: { disclosures: Disclosures }) {
  return (
    <FoldedSection title="Veröffentlichungspflichtige Angaben">
      {disclosures.note && <p>{disclosures.note}</p>}
      {disclosures.sections.map((section, i) => (
        <div key={`${i}-${section.heading}`} className="flex flex-col gap-1.5">
          {section.heading && (
            <h4 className="font-semibold">{section.heading}</h4>
          )}
          {section.entries.map((entry, j) => (
            <ul
              // biome-ignore lint/suspicious/noArrayIndexKey: entries have no id and never reorder
              key={j}
              className="border-l-2 border-[var(--daily-border)] pl-2.5"
            >
              {entry.lines.map((line, k) => (
                <li
                  // biome-ignore lint/suspicious/noArrayIndexKey: lines have no id and never reorder
                  key={k}
                  className={cn(
                    k === 0 && line.level === 0 && 'font-medium',
                    line.level > 0 && cn('pl-3', MUTED_TEXT),
                  )}
                >
                  {line.text}
                </li>
              ))}
            </ul>
          ))}
        </div>
      ))}
      {disclosures.link && (
        <SourceLink href={disclosures.link}>
          {disclosures.link_phrase ?? 'Erläuterungen des Abgeordneten'}
        </SourceLink>
      )}
    </FoldedSection>
  );
}

/** A member of the government or the Bundesrat who sits in no Bundestag
 * Fraktion: no Bundestag profile to show, only party and office. */
function OutsideProfile({ politician }: { politician: Politician }) {
  const institutions = [
    ...new Set(politician.offices.map((office) => office.institution)),
  ];
  return (
    <>
      {politician.partei && (
        <div className="grid grid-cols-2 gap-1.5">
          <Tile label="Partei" value={politician.partei} />
        </div>
      )}
      <p className={cn('text-[14px]', MUTED_TEXT)}>
        {politician.name} ist kein Mitglied des Bundestages und spricht dort für{' '}
        {institutions.join(' und ') || 'die Bundesregierung'}.
      </p>
    </>
  );
}

function Profile({ politician }: { politician: Politician }) {
  if (politician.source === 'roster') {
    return <OutsideProfile politician={politician} />;
  }
  const tenure = tenureLabel(politician);
  const mandate = mandateLabel(politician);
  return (
    <>
      {(tenure || politician.beruf || mandate) && (
        <div className="grid grid-cols-2 gap-1.5">
          {tenure && <Tile label="Im Bundestag seit" value={tenure} />}
          {politician.beruf && <Tile label="Beruf" value={politician.beruf} />}
          {mandate && <Tile label="Mandat" value={mandate} wide />}
        </div>
      )}
      <Committees politician={politician} />
      <OtherGremien politician={politician} />
      {politician.votes && politician.votes.length > 0 && (
        <RollCallList votes={politician.votes} bioUrl={politician.bio_url} />
      )}
      {politician.disclosures && (
        <DisclosureList disclosures={politician.disclosures} />
      )}
      <footer className={cn('flex flex-col gap-0.5 text-[12px]', MUTED_TEXT)}>
        {politician.photo_credit && (
          <span>Foto: {politician.photo_credit}</span>
        )}
        <span>
          Quelle: Deutscher Bundestag
          {politician.source_stand && `, Stand ${politician.source_stand}`}
        </span>
        {politician.bio_url && (
          <SourceLink href={politician.bio_url}>
            Profil auf bundestag.de
          </SourceLink>
        )}
      </footer>
    </>
  );
}

function Loading() {
  return (
    <div aria-hidden className="flex flex-col gap-2">
      <div className="h-14 animate-pulse rounded-lg bg-[var(--daily-surface)]" />
      <div className="h-24 animate-pulse rounded-lg bg-[var(--daily-surface)]" />
    </div>
  );
}

/**
 * What the Bundestag publishes about one speaker: offices, how long they
 * have been a member, Gremien and the Veröffentlichungspflichtige Angaben.
 * A bottom sheet on phones, a dialog from md up.
 */
export function PoliticianSheet({
  open,
  photos,
  container,
  onClose,
}: {
  open: OpenSpeaker | null;
  /** The debate's portraits by MdB ID, shown before the record loads. */
  photos: Record<string, string>;
  /** The content of the view the sheet opens over, see
   * `ResponsiveDialogContent`. */
  container?: HTMLElement | null;
  onClose: () => void;
}) {
  const isDesktop = useIsDesktop();
  const viewer = useMediaViewer();
  // Kept while the sheet animates out, so it does not empty first.
  const [shown, setShown] = useState(open);
  if (open && open !== shown) {
    setShown(open);
  }
  const { politician, loading } = usePolitician(shown?.speaker.mdb_id ?? null);
  if (!shown) {
    return null;
  }
  const { speaker, party } = shown;
  const photo =
    politician?.photo_url ??
    (speaker.mdb_id ? photos[speaker.mdb_id] : undefined);
  const offices = politician ? officeLines(politician) : [];
  const speech = speakerViewerSource(speaker, party);

  return (
    <ResponsiveDialog
      open={open !== null}
      onOpenChange={(isOpen) => !isOpen && onClose()}
    >
      <ResponsiveDialogContent
        container={container}
        className={cn(
          DAILY_THEME_CLASSES,
          'flex max-h-[90dvh] flex-col gap-0 border-[var(--daily-border)] bg-[var(--daily-canvas)] p-0 text-[var(--daily-ink)] md:max-w-lg',
        )}
      >
        <div className="flex min-h-0 flex-col gap-4 overflow-y-auto overscroll-contain px-4 pb-6 pt-3 md:pt-6">
          <header className="flex items-center gap-3 md:pr-8">
            <Avatar photo={photo} party={party} partei={politician?.partei} />
            <div className="min-w-0 flex-1 leading-tight">
              <ResponsiveDialogTitle className="text-left text-[18px] font-bold">
                {politician ? displayName(politician) : speaker.name}
              </ResponsiveDialogTitle>
              {/* Offices only: the party is the badge under the photo.
                  Without an office the dialog is still described, for
                  screen readers only. */}
              <ResponsiveDialogDescription
                className={cn(
                  'mt-0.5 text-left text-[13px]',
                  MUTED_TEXT,
                  offices.length === 0 && 'sr-only',
                )}
              >
                {offices.length > 0
                  ? offices.map((office, i) => (
                      <span key={office}>
                        {i > 0 && ' · '}
                        <GlossaryLabel label={office} />
                      </span>
                    ))
                  : speakerPartyLabel(party, politician?.partei)}
              </ResponsiveDialogDescription>
            </div>
            {!isDesktop && (
              <ResponsiveDialogClose
                className={cn(
                  FOCUS_RING,
                  'flex size-10 shrink-0 items-center justify-center rounded-full bg-[var(--daily-surface)]',
                )}
              >
                <XIcon className="size-4" aria-hidden />
                <span className="sr-only">Schließen</span>
              </ResponsiveDialogClose>
            )}
          </header>
          {speech && (
            <button
              type="button"
              onClick={() =>
                viewer
                  ? viewer.openSource(speech)
                  : window.open(speech.url, '_blank')
              }
              className={cn(
                FOCUS_RING,
                'flex min-h-11 items-center gap-2.5 rounded-lg border border-[var(--daily-border)] py-1.5 pl-1.5 pr-3 text-left hover:bg-[var(--daily-surface)]',
              )}
            >
              <span
                aria-hidden
                className="flex size-8 items-center justify-center rounded-full bg-[var(--daily-ink)] text-[var(--daily-canvas)]"
              >
                <PlayIcon className="size-3 fill-current" />
              </span>
              <span className="flex-1 text-[14px] font-semibold">
                Rede in dieser Debatte ansehen
              </span>
              {speaker.duration ? (
                <span className={cn('text-[12px]', MUTED_TEXT)}>
                  {formatTimestamp(speaker.duration)}
                </span>
              ) : null}
            </button>
          )}
          {loading ? (
            <Loading />
          ) : politician ? (
            <Profile politician={politician} />
          ) : (
            <p className={cn('text-[14px]', MUTED_TEXT)}>
              {isNonMember(speaker)
                ? `${speaker.name} ist kein Mitglied des Bundestages, daher gibt es hier kein Bundestagsprofil.`
                : 'Für diese Person liegt kein Profil des Bundestages vor.'}
            </p>
          )}
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}
