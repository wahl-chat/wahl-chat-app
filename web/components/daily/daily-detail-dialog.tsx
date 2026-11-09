'use client';

import { useMediaViewer } from '@/components/providers/media-viewer-provider';
import StickyInput from '@/components/sticky-input';
import { FEED_CHAT_ENABLED, feedChatHref } from '@/lib/daily/chat-handoff';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import {
  type DetailItem,
  type SectionItem,
  type VoteItem,
  openingParty,
  protocolLabel,
  sectionTopics,
  suggestedQuestions,
} from '@/lib/daily/items';
import { shareItem } from '@/lib/daily/share';
import { numberedSources } from '@/lib/daily/sources';
import { cn } from '@/lib/utils';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { ChevronLeftIcon, ShareIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useId, useState } from 'react';
import { FOCUS_RING, MUTED_TEXT, SECTION_LABEL } from './card-styles';
import { Hemicycle, PartyVoteBreakdown, SeatLegend } from './hemicycle';
import { PartyPositions, orderedPositions } from './party-positions';
import { HeatInfo } from './plenary-card';
import { SourcePills } from './source-pills';
import { SectionMediaFrame, sectionMedia } from './speech-videos';
import { TopicMeta } from './topic-chip';
import { OutcomeBadge } from './vote-card';
import { PartyVoteTable, SourceLink } from './vote-panels';

const longDayFormat = new Intl.DateTimeFormat('de-DE', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
});

const ICON_BUTTON = cn(
  FOCUS_RING,
  'flex size-11 items-center justify-center rounded-full hover:bg-[var(--daily-surface)]',
);

function placeholderFor(item: DetailItem): string {
  return item.kind === 'vote'
    ? 'Frag zu dieser Abstimmung …'
    : 'Frag zu dieser Debatte …';
}

/**
 * "Mehr wissen? Frag nach.": suggested questions and a free input, both
 * handing the question plus the item's context to the chat.
 */
export function AskPanel({
  item,
  withSuggestions = true,
  className,
}: {
  item: DetailItem;
  withSuggestions?: boolean;
  className?: string;
}) {
  const router = useRouter();
  const ask = (question: string) => {
    if (question.trim()) {
      router.push(feedChatHref(item, question));
    }
  };
  const suggestions = withSuggestions ? suggestedQuestions(item) : [];
  return (
    <div className={className}>
      {suggestions.length > 0 && (
        <p className="px-4 pb-2 pt-3 text-[15px] font-semibold">
          Mehr wissen? Frag nach.
        </p>
      )}
      <StickyInput
        isLoading={false}
        onSubmit={ask}
        quickReplies={suggestions}
        placeholder={placeholderFor(item)}
        className="static mx-2 pb-3 md:pb-3"
      />
    </div>
  );
}

function SectionDetail({
  item,
  heat,
}: {
  item: SectionItem;
  heat: number | undefined;
}) {
  const { section, digest } = item;
  const media = sectionMedia(section);
  const protocol = digest.session?.protocols[0];
  const points = section.key_points ?? [];
  const openedBy = openingParty(section);
  const sources = numberedSources(
    section,
    orderedPositions(section.positions ?? [], openedBy).map((p) => p.party_id),
  );
  return (
    <>
      {media && <SectionMediaFrame media={media} />}
      <div className="flex flex-col gap-4 px-4 pt-4">
        <TopicMeta
          topics={sectionTopics(section)}
          trailing={heat ? <HeatInfo heat={heat} /> : null}
        />
        <DialogPrimitive.Title className="hyphens-auto break-words text-[22px] font-bold leading-snug">
          {section.headline}
        </DialogPrimitive.Title>
        {/* The card's teaser, here in full, so the detail reads on from it. */}
        {section.summary && (
          <p className="text-[17px] leading-relaxed">{section.summary}</p>
        )}
        {points.length > 0 && (
          <section className="flex flex-col gap-1.5">
            <h3 className={SECTION_LABEL}>Kernpunkte</h3>
            <ul className="list-disc space-y-1.5 pl-5 text-[15px] leading-relaxed">
              {points.map((point, i) => (
                <li key={`${i}-${point}`}>
                  {point}
                  <SourcePills
                    numbers={sources.keyPoint(i)}
                    sources={sources}
                  />
                </li>
              ))}
            </ul>
          </section>
        )}
        {section.positions && section.positions.length > 0 && (
          <section className="flex flex-col gap-1.5">
            <h3 className={SECTION_LABEL}>Wer sagt was</h3>
            <PartyPositions
              positions={section.positions}
              openedBy={openedBy}
              sources={sources}
            />
          </section>
        )}
        {protocol &&
          (protocol.pdf_url ? (
            <SourceLink href={protocol.pdf_url}>
              Quelle: Plenarprotokoll {protocolLabel(digest)}
            </SourceLink>
          ) : (
            <p className={cn('text-[15px]', MUTED_TEXT)}>
              Quelle: Plenarprotokoll {protocolLabel(digest)}
            </p>
          ))}
      </div>
    </>
  );
}

function VoteDetail({ item }: { item: VoteItem }) {
  const { vote, digest } = item;
  const protocol = protocolLabel(digest);
  const about = vote.summary ?? vote.description;
  // One Fraktion at a time, picked in the chart or the list; picking it again
  // closes it.
  const [selected, setSelected] = useState<string | null>(null);
  const select = (partyId: string) =>
    setSelected((current) => (current === partyId ? null : partyId));
  const selectedParty = vote.parties.find((p) => p.party_id === selected);
  const breakdownId = useId();
  return (
    <div className="flex flex-col gap-4 px-4 pt-4">
      <div className="flex items-center justify-between gap-3">
        <TopicMeta
          topics={vote.topics}
          suffix={protocol ? `Protokoll ${protocol}` : null}
        />
        <OutcomeBadge outcome={vote.outcome} />
      </div>
      <DialogPrimitive.Title className="hyphens-auto break-words text-[22px] font-bold leading-snug">
        {vote.short_title}
      </DialogPrimitive.Title>
      <Hemicycle
        parties={vote.parties}
        selected={selected}
        onSelect={select}
        className="mx-auto max-w-md"
      />
      <SeatLegend parties={vote.parties} />
      {selectedParty && (
        <PartyVoteBreakdown party={selectedParty} id={breakdownId} />
      )}
      {about && (
        <section className="rounded-xl bg-[var(--daily-surface)] p-4">
          <h3 className={SECTION_LABEL}>Worum ging es?</h3>
          <p className="mt-1 text-[15px] leading-relaxed">{about}</p>
        </section>
      )}
      <section className="flex flex-col gap-1">
        <h3 className={SECTION_LABEL}>So haben die Fraktionen gestimmt</h3>
        <PartyVoteTable
          vote={vote}
          selected={selected}
          onSelect={select}
          breakdownId={breakdownId}
        />
      </section>
      <p className={cn('text-[13px]', MUTED_TEXT)}>
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

type Props = {
  item: DetailItem | null;
  /** Day-relative heat of the item, see `dayHeat`. */
  heat: number | undefined;
  onClose: () => void;
};

/** The phone media viewer is a vaul Drawer, which brings its own copy of
 * Radix: this dialog does not see it as a layer above itself, so a tap on
 * the Drawer's backdrop, or Escape, would close both. */
function isViewerLayer(target: EventTarget | null): boolean {
  return (
    target instanceof Element &&
    target.closest('[data-vaul-overlay], [data-vaul-drawer]') !== null
  );
}

/**
 * The opened item: a little more than its card. Full screen on phones, a
 * centred column from md up.
 */
export function DailyDetailDialog({ item, heat, onClose }: Props) {
  // An outside tap or Escape closes the source viewer first, and only a
  // second one this view.
  const viewer = useMediaViewer();
  const viewerOpen = viewer?.isOpen ?? false;
  const keepOpen = (event: Event) => {
    if (viewerOpen || isViewerLayer(event.target)) {
      event.preventDefault();
    }
  };
  // Escape reaches this handler first, and suppressing it here also stops
  // the Drawer's own, so the viewer is closed from here.
  const closeViewerFirst = (event: KeyboardEvent) => {
    if (viewerOpen) {
      event.preventDefault();
      viewer?.close();
    }
  };
  const context = item
    ? `${item.kind === 'vote' ? 'Abstimmung' : 'Plenarsitzung'} · ${longDayFormat.format(new Date(`${item.digest.date}T00:00:00Z`))}`
    : '';

  return (
    <DialogPrimitive.Root
      open={item !== null}
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <DialogPrimitive.Content
          onPointerDownOutside={keepOpen}
          onInteractOutside={keepOpen}
          onEscapeKeyDown={closeViewerFirst}
          className={cn(
            DAILY_THEME_CLASSES,
            'fixed inset-0 z-50 flex flex-col bg-[var(--daily-canvas)] focus:outline-none md:inset-auto md:left-1/2 md:top-1/2 md:h-[90dvh] md:w-full md:max-w-screen-sm md:-translate-x-1/2 md:-translate-y-1/2 md:overflow-hidden md:rounded-xl',
          )}
        >
          {item && (
            <>
              <header className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--daily-border)] px-2 py-1.5">
                <DialogPrimitive.Close
                  aria-label="Zurück zum Feed"
                  className={ICON_BUTTON}
                >
                  <ChevronLeftIcon className="size-6" />
                </DialogPrimitive.Close>
                <DialogPrimitive.Description
                  className={cn('truncate text-[15px]', MUTED_TEXT)}
                >
                  {context}
                </DialogPrimitive.Description>
                <button
                  type="button"
                  aria-label="Teilen"
                  onClick={() => shareItem(item)}
                  className={ICON_BUTTON}
                >
                  <ShareIcon className="size-5" />
                </button>
              </header>
              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain pb-6">
                {item.kind === 'vote' ? (
                  <VoteDetail item={item} />
                ) : (
                  <SectionDetail item={item} heat={heat} />
                )}
              </div>
              {FEED_CHAT_ENABLED && (
                <AskPanel
                  item={item}
                  className="shrink-0 border-t border-[var(--daily-border)]"
                />
              )}
            </>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
