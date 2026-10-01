'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { formatFeedDay } from '@/lib/daily/feed';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import { isCloseVote } from '@/lib/daily/hemicycle';
import {
  otherTopicsSentence,
  splitSections,
  topicTitle,
} from '@/lib/daily/topics';
import type { DigestSession, DigestVote } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ChevronLeftIcon, ChevronRightIcon, FileTextIcon } from 'lucide-react';
import { useEffect, useState } from 'react';
import { INK_LABEL, MUTED_TEXT, PRESSABLE } from './card-styles';
import type { DetailItem } from './detail-items';
import { Hemicycle, VoteTally } from './hemicycle';
import { OtherTopicsQuote } from './plenary-card';
import TopicChip from './topic-chip';
import { CloseVoteSticker, OutcomeBadge, VoteTotalsLine } from './vote-card';
import { PartyVoteTable, SourceLink } from './vote-panels';

// A small brutalist key for in-dialog actions.
const KEY_BUTTON = cn(
  PRESSABLE,
  'inline-flex h-9 items-center gap-1 rounded-[4px] border-2 border-[var(--daily-ink)] bg-[var(--daily-surface)] px-3 text-xs font-bold shadow-[3px_3px_0_0_var(--daily-ink)] disabled:pointer-events-none disabled:opacity-35 disabled:shadow-none',
);

type Props = {
  items: DetailItem[];
  index: number | null;
  selectedTopics: string[];
  onIndexChange: (index: number | null) => void;
};

export function DailyDetailDialog({
  items,
  index,
  selectedTopics,
  onIndexChange,
}: Props) {
  const item = index === null ? undefined : items[index];
  const canPrev = index !== null && index > 0;
  const canNext = index !== null && index < items.length - 1;

  useEffect(() => {
    if (index === null) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'ArrowLeft' && index > 0) {
        onIndexChange(index - 1);
      } else if (event.key === 'ArrowRight' && index < items.length - 1) {
        onIndexChange(index + 1);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [index, items.length, onIndexChange]);

  return (
    <ResponsiveDialog
      open={item !== undefined}
      onOpenChange={(open) => !open && onIndexChange(null)}
    >
      <ResponsiveDialogContent
        className={cn(
          DAILY_THEME_CLASSES,
          'flex max-h-[90dvh] flex-col border-2 border-[var(--daily-ink)] bg-[var(--daily-canvas)] md:max-w-2xl md:rounded-md md:shadow-[6px_6px_0_0_var(--daily-ink)]',
        )}
      >
        {item && (
          <>
            <ResponsiveDialogHeader className="gap-2 text-left">
              <ResponsiveDialogDescription
                className={cn(INK_LABEL, 'text-[var(--daily-canvas)]')}
              >
                {item.digest.parliament_name} ·{' '}
                {formatFeedDay(item.digest.date)}
              </ResponsiveDialogDescription>
              <ResponsiveDialogTitle className="font-display text-2xl font-black leading-tight md:text-3xl">
                {item.kind === 'vote'
                  ? item.vote.short_title
                  : 'Plenarsitzung: die Themen'}
              </ResponsiveDialogTitle>
            </ResponsiveDialogHeader>

            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 pb-2 md:px-0">
              {item.kind === 'vote' ? (
                <VoteDetail vote={item.vote} />
              ) : (
                item.digest.session && (
                  <SessionDetail
                    key={item.key}
                    session={item.digest.session}
                    selectedTopics={selectedTopics}
                  />
                )
              )}
            </div>

            <nav
              className="flex items-center justify-between gap-2 border-t-2 border-[var(--daily-ink)] px-4 py-3 md:px-0 md:pb-0"
              aria-label="Zwischen den Inhalten dieses Tages wechseln"
            >
              <button
                type="button"
                className={KEY_BUTTON}
                disabled={!canPrev}
                onClick={() => canPrev && onIndexChange(index - 1)}
              >
                <ChevronLeftIcon className="size-4" /> Zurück
              </button>
              <span className="font-display text-lg font-black tabular-nums">
                {(index ?? 0) + 1} / {items.length}
              </span>
              <button
                type="button"
                className={KEY_BUTTON}
                disabled={!canNext}
                onClick={() => canNext && onIndexChange(index + 1)}
              >
                Weiter <ChevronRightIcon className="size-4" />
              </button>
            </nav>
          </>
        )}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

function VoteDetail({ vote }: { vote: DigestVote }) {
  return (
    <div className="flex flex-col gap-5 pt-2">
      <div className="flex flex-wrap items-center gap-2">
        {vote.topics.map((topic) => (
          <TopicChip key={topic} topic={topic} />
        ))}
        <span className="ml-auto flex items-center gap-2">
          {isCloseVote(vote.parties) && <CloseVoteSticker />}
          <OutcomeBadge outcome={vote.outcome} />
        </span>
      </div>
      {vote.summary && (
        <p className="text-base leading-relaxed">{vote.summary}</p>
      )}
      {vote.description && (
        <p className={cn('text-sm leading-relaxed', MUTED_TEXT)}>
          {vote.description}
        </p>
      )}
      <div className="flex flex-col items-center gap-3">
        <Hemicycle parties={vote.parties} className="max-w-md" />
        <VoteTally parties={vote.parties} />
        <VoteTotalsLine vote={vote} />
      </div>
      <PartyVoteTable vote={vote} />
      <p className={cn('text-xs', MUTED_TEXT)}>Originaltitel: {vote.title}</p>
      {vote.citation_url && (
        <SourceLink href={vote.citation_url}>
          Abstimmung auf abgeordnetenwatch.de
        </SourceLink>
      )}
    </div>
  );
}

function SessionDetail({
  session,
  selectedTopics,
}: {
  session: DigestSession;
  selectedTopics: string[];
}) {
  const [showAll, setShowAll] = useState(false);
  const { visible, hidden } = splitSections(
    session.sections,
    showAll ? [] : selectedTopics,
  );

  return (
    <div className="flex flex-col gap-7 pt-2">
      {visible.map((section, i) => (
        <section
          key={`${i}:${section.headline}`}
          className="grid grid-cols-[auto_1fr] gap-x-4"
        >
          <span className="font-display text-4xl font-black leading-none">
            {String(i + 1).padStart(2, '0')}
          </span>
          <div className="flex min-w-0 flex-col gap-2">
            <TopicChip topic={section.topic} />
            <h4 className="font-display text-xl font-extrabold leading-tight">
              {section.headline}
            </h4>
            <p className="text-[15px] leading-relaxed">{section.summary}</p>
            {section.video_url && (
              <video
                controls
                // Metadata plus a media fragment makes the browser decode one
                // frame to show as the thumbnail; with preload="none" the player
                // stays an empty grey box until it is started.
                preload="metadata"
                src={`${section.video_url.split('#')[0]}#t=0.5`}
                className="mt-1 aspect-video w-full rounded-[4px] border-2 border-[var(--daily-ink)] bg-black shadow-[4px_4px_0_0_var(--daily-ink)]"
              />
            )}
            <p className={cn('text-xs font-medium', MUTED_TEXT)}>
              {section.agenda_items.join(' · ')}
            </p>
            <ul className="flex flex-col gap-0.5">
              {section.citations.map((citation) => (
                <li key={citation.url}>
                  <SourceLink href={citation.url}>{citation.title}</SourceLink>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ))}

      <OtherTopicsQuote>
        {otherTopicsSentence(hidden, session.other_topics)}
      </OtherTopicsQuote>
      {hidden.length > 0 && (
        <button
          type="button"
          className={cn(KEY_BUTTON, 'h-auto w-fit py-2 text-left')}
          onClick={() => setShowAll(true)}
        >
          Alle Themen anzeigen (
          {[...new Set(hidden.map((s) => topicTitle(s.topic)))].join(', ')})
        </button>
      )}

      <div className="flex flex-col gap-1.5 border-t-2 border-[var(--daily-ink)] pt-3">
        {session.protocols.map((protocol) =>
          protocol.pdf_url ? (
            <SourceLink key={protocol.protocol_id} href={protocol.pdf_url}>
              <FileTextIcon className="size-3.5" />
              Plenarprotokoll {protocol.protocol_id} (PDF)
            </SourceLink>
          ) : (
            <span
              key={protocol.protocol_id}
              className={cn('text-xs', MUTED_TEXT)}
            >
              Plenarprotokoll {protocol.protocol_id}
            </span>
          ),
        )}
        <p className={cn('text-xs', MUTED_TEXT)}>
          Automatisch aus den Redebeiträgen zusammengefasst. Maßgeblich ist das
          Protokoll.
        </p>
      </div>
    </div>
  );
}
