'use client';

import StickyInput from '@/components/sticky-input';
import { feedChatHref } from '@/lib/daily/chat-handoff';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import {
  type DetailItem,
  type SectionItem,
  type VoteItem,
  openingParty,
  protocolLabel,
  suggestedQuestions,
} from '@/lib/daily/items';
import { topicTitle } from '@/lib/daily/topics';
import { cn } from '@/lib/utils';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { ChevronLeftIcon, ShareIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { FOCUS_RING, MUTED_TEXT, SECTION_LABEL } from './card-styles';
import { Hemicycle, SeatLegend } from './hemicycle';
import { PartyPositions } from './party-positions';
import { SectionMediaFrame, sectionMedia } from './speech-videos';
import { TopicDot, TopicMeta } from './topic-chip';
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
  return (
    <>
      {media && <SectionMediaFrame media={media} />}
      <div className="flex flex-col gap-4 px-4 pt-4">
        <p className={cn('flex items-center gap-1.5 text-[13px]', MUTED_TEXT)}>
          <TopicDot topic={section.topic} />
          {topicTitle(section.topic)}
          {heat ? ` · Hitzigkeit ${heat}/5` : ''}
        </p>
        <DialogPrimitive.Title className="hyphens-auto break-words text-[22px] font-bold leading-snug">
          {section.headline}
        </DialogPrimitive.Title>
        <section className="flex flex-col gap-1.5">
          <h3 className={SECTION_LABEL}>Kurz gesagt</h3>
          {points.length > 0 ? (
            <ul className="list-disc space-y-1.5 pl-5 text-[15px] leading-relaxed">
              {points.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          ) : (
            <p className="text-[15px] leading-relaxed">{section.summary}</p>
          )}
        </section>
        {section.positions && section.positions.length > 0 && (
          <section className="flex flex-col gap-1.5">
            <h3 className={SECTION_LABEL}>Wer sagt was</h3>
            <PartyPositions
              positions={section.positions}
              openedBy={openingParty(section)}
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
  return (
    <div className="flex flex-col gap-4 px-4 pt-4">
      <div className="flex items-center justify-between gap-3">
        <TopicMeta
          topics={vote.topics}
          short
          suffix={protocol ? `Protokoll ${protocol}` : null}
        />
        <OutcomeBadge outcome={vote.outcome} />
      </div>
      <DialogPrimitive.Title className="hyphens-auto break-words text-[22px] font-bold leading-snug">
        {vote.short_title}
      </DialogPrimitive.Title>
      <Hemicycle parties={vote.parties} className="mx-auto max-w-md" />
      <SeatLegend parties={vote.parties} />
      {about && (
        <section className="rounded-xl bg-[var(--daily-surface)] p-4">
          <h3 className={SECTION_LABEL}>Worum ging es?</h3>
          <p className="mt-1 text-[15px] leading-relaxed">{about}</p>
        </section>
      )}
      <section className="flex flex-col gap-1">
        <h3 className={SECTION_LABEL}>So haben die Fraktionen gestimmt</h3>
        <PartyVoteTable vote={vote} />
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

async function share(item: DetailItem) {
  const url = window.location.href;
  const title =
    item.kind === 'vote' ? item.vote.short_title : item.section.headline;
  try {
    if (navigator.share) {
      await navigator.share({ title, url });
      return;
    }
    await navigator.clipboard.writeText(url);
    toast.success('Link kopiert');
  } catch {
    // The share sheet was dismissed.
  }
}

type Props = {
  item: DetailItem | null;
  /** Day-relative heat of the item, see `dayHeat`. */
  heat: number | undefined;
  onClose: () => void;
};

/**
 * The opened item: a little more than its card, then straight to the chat.
 * Full screen on phones, a centred column from md up.
 */
export function DailyDetailDialog({ item, heat, onClose }: Props) {
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
                  onClick={() => share(item)}
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
              <AskPanel
                item={item}
                className="shrink-0 border-t border-[var(--daily-border)]"
              />
            </>
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
