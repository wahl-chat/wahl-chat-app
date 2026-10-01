'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { Button } from '@/components/ui/button';
import { formatFeedDay } from '@/lib/daily/feed';
import { sortBySeating } from '@/lib/daily/seating-order';
import {
  otherTopicsSentence,
  splitSections,
  topicTitle,
} from '@/lib/daily/topics';
import type { DigestSession, DigestVote } from '@/lib/firebase/firebase.types';
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ExternalLinkIcon,
  FileTextIcon,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import type { DetailItem } from './detail-items';
import { Hemicycle, SeatLegend } from './hemicycle';
import TopicChip from './topic-chip';
import { OutcomeBadge, PartyKey, VoteTotalsLine } from './vote-card';

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
      <ResponsiveDialogContent className="flex max-h-[90dvh] flex-col md:max-w-2xl">
        {item && (
          <>
            <ResponsiveDialogHeader className="text-left">
              <ResponsiveDialogDescription>
                {item.digest.parliament_name} ·{' '}
                {formatFeedDay(item.digest.date)}
              </ResponsiveDialogDescription>
              <ResponsiveDialogTitle className="leading-snug">
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
              className="flex items-center justify-between gap-2 border-t border-border px-4 py-3 md:px-0 md:pb-0"
              aria-label="Zwischen den Inhalten dieses Tages wechseln"
            >
              <Button
                variant="ghost"
                size="sm"
                disabled={!canPrev}
                onClick={() => canPrev && onIndexChange(index - 1)}
              >
                <ChevronLeftIcon /> Zurück
              </Button>
              <span className="text-xs tabular-nums text-muted-foreground">
                {(index ?? 0) + 1} / {items.length}
              </span>
              <Button
                variant="ghost"
                size="sm"
                disabled={!canNext}
                onClick={() => canNext && onIndexChange(index + 1)}
              >
                Weiter <ChevronRightIcon />
              </Button>
            </nav>
          </>
        )}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

function VoteDetail({ vote }: { vote: DigestVote }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5">
        {vote.topics.map((topic) => (
          <TopicChip key={topic} topic={topic} />
        ))}
        <span className="ml-auto">
          <OutcomeBadge outcome={vote.outcome} />
        </span>
      </div>
      {vote.summary && <p className="text-sm">{vote.summary}</p>}
      <div className="flex flex-col items-center gap-2">
        <Hemicycle parties={vote.parties} className="max-w-md" />
        <VoteTotalsLine vote={vote} />
        <SeatLegend />
        <PartyKey vote={vote} />
      </div>
      <table className="w-full text-sm tabular-nums">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b border-border">
            <th className="py-1.5 text-left font-medium">Fraktion</th>
            <th className="py-1.5 text-right font-medium">Ja</th>
            <th className="py-1.5 text-right font-medium">Nein</th>
            <th className="py-1.5 text-right font-medium">Enth.</th>
            <th className="py-1.5 text-right font-medium">Abw.</th>
          </tr>
        </thead>
        <tbody>
          {sortBySeating(vote.parties).map((party) => (
            <tr key={party.party_id} className="border-b border-border/60">
              <td className="flex items-center gap-2 py-1.5">
                <span
                  className="inline-block size-2.5 rounded-full border border-border"
                  style={{ backgroundColor: party.color }}
                />
                {party.name}
              </td>
              <td className="py-1.5 text-right">{party.yes}</td>
              <td className="py-1.5 text-right">{party.no}</td>
              <td className="py-1.5 text-right">{party.abstain}</td>
              <td className="py-1.5 text-right">{party.no_show}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-muted-foreground">
        Originaltitel: {vote.title}
      </p>
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
    <div className="flex flex-col gap-5">
      {visible.map((section, i) => (
        <section
          key={`${i}:${section.headline}`}
          className="flex flex-col gap-1.5"
        >
          <TopicChip topic={section.topic} />
          <h4 className="font-semibold leading-snug">{section.headline}</h4>
          <p className="text-sm">{section.summary}</p>
          {section.video_url && (
            <video
              controls
              // Metadata plus a media fragment makes the browser decode one
              // frame to show as the thumbnail; with preload="none" the player
              // stays an empty grey box until it is started.
              preload="metadata"
              src={`${section.video_url.split('#')[0]}#t=0.5`}
              className="mt-1 aspect-video w-full rounded-md bg-black"
            />
          )}
          <p className="text-xs text-muted-foreground">
            {section.agenda_items.join(' · ')}
          </p>
          <ul className="flex flex-col gap-0.5">
            {section.citations.map((citation) => (
              <li key={citation.url}>
                <SourceLink href={citation.url}>{citation.title}</SourceLink>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <p className="text-sm text-muted-foreground">
        {otherTopicsSentence(hidden, session.other_topics)}
      </p>
      {hidden.length > 0 && (
        <Button
          variant="outline"
          size="sm"
          className="w-fit"
          onClick={() => setShowAll(true)}
        >
          Alle Themen anzeigen (
          {[...new Set(hidden.map((s) => topicTitle(s.topic)))].join(', ')})
        </Button>
      )}

      <div className="flex flex-col gap-1 border-t border-border pt-3">
        {session.protocols.map((protocol) =>
          protocol.pdf_url ? (
            <SourceLink key={protocol.protocol_id} href={protocol.pdf_url}>
              <FileTextIcon className="size-3.5" />
              Plenarprotokoll {protocol.protocol_id} (PDF)
            </SourceLink>
          ) : (
            <span
              key={protocol.protocol_id}
              className="text-xs text-muted-foreground"
            >
              Plenarprotokoll {protocol.protocol_id}
            </span>
          ),
        )}
        <p className="text-xs text-muted-foreground">
          Automatisch aus den Redebeiträgen zusammengefasst. Maßgeblich ist das
          Protokoll.
        </p>
      </div>
    </div>
  );
}

function SourceLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs font-medium underline-offset-2 hover:underline"
    >
      {children}
      <ExternalLinkIcon className="size-3" />
    </a>
  );
}
