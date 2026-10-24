'use client';

import StickyInput from '@/components/sticky-input';
import { feedChatHref } from '@/lib/daily/chat-handoff';
import { DAILY_THEME_CLASSES } from '@/lib/daily/fonts';
import type { FeedStrings } from '@/lib/daily/i18n';
import {
  type DetailItem,
  type SectionItem,
  type VoteItem,
  openingParty,
  protocolLabel,
  suggestedQuestions,
} from '@/lib/daily/items';
import { shareItem } from '@/lib/daily/share';
import { topicTitle } from '@/lib/daily/topics';
import { cn } from '@/lib/utils';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { ChevronLeftIcon, ShareIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { FOCUS_RING, MUTED_TEXT, SECTION_LABEL } from './card-styles';
import { useFeedLocale } from './feed-locale';
import { Hemicycle, SeatLegend } from './hemicycle';
import { PartyPositions } from './party-positions';
import { SectionMediaFrame, sectionMedia } from './speech-videos';
import { TopicDot, TopicMeta } from './topic-chip';
import { OutcomeBadge } from './vote-card';
import { PartyVoteTable, SourceLink } from './vote-panels';

function longDayFormat(intl: string) {
  return new Intl.DateTimeFormat(intl, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

const ICON_BUTTON = cn(
  FOCUS_RING,
  'flex size-11 items-center justify-center rounded-full hover:bg-[var(--daily-surface)]',
);

function placeholderFor(item: DetailItem, t: FeedStrings): string {
  return item.kind === 'vote' ? t.askVote : t.askDebate;
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
  const { t } = useFeedLocale();
  const ask = (question: string) => {
    if (question.trim()) {
      router.push(feedChatHref(item, question));
    }
  };
  const suggestions = withSuggestions ? suggestedQuestions(item) : [];
  return (
    <div className={className}>
      {suggestions.length > 0 && (
        <p className="px-4 pb-2 pt-3 text-[15px] font-semibold">{t.askMore}</p>
      )}
      <StickyInput
        isLoading={false}
        onSubmit={ask}
        quickReplies={suggestions}
        placeholder={placeholderFor(item, t)}
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
  const { t, locale } = useFeedLocale();
  const { section, digest } = item;
  const media = sectionMedia(section, t);
  const protocol = digest.session?.protocols[0];
  const points = section.key_points ?? [];
  return (
    <>
      {media && <SectionMediaFrame media={media} />}
      <div className="flex flex-col gap-4 px-4 pt-4">
        <p className={cn('flex items-center gap-1.5 text-[13px]', MUTED_TEXT)}>
          <TopicDot topic={section.topic} />
          {topicTitle(section.topic, locale)}
          {heat ? ` · ${t.heatShort(heat)}` : ''}
        </p>
        <DialogPrimitive.Title className="hyphens-auto break-words text-[22px] font-bold leading-snug">
          {section.headline}
        </DialogPrimitive.Title>
        <section className="flex flex-col gap-1.5">
          <h3 className={SECTION_LABEL}>{t.inShort}</h3>
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
            <h3 className={SECTION_LABEL}>{t.whoSaysWhat}</h3>
            <PartyPositions
              positions={section.positions}
              openedBy={openingParty(section)}
            />
          </section>
        )}
        {protocol &&
          (protocol.pdf_url ? (
            <SourceLink href={protocol.pdf_url}>
              {t.source(protocolLabel(digest) ?? '')}
            </SourceLink>
          ) : (
            <p className={cn('text-[15px]', MUTED_TEXT)}>
              {t.source(protocolLabel(digest) ?? '')}
            </p>
          ))}
      </div>
    </>
  );
}

function VoteDetail({ item }: { item: VoteItem }) {
  const { t } = useFeedLocale();
  const { vote, digest } = item;
  const protocol = protocolLabel(digest);
  const about = vote.summary ?? vote.description;
  return (
    <div className="flex flex-col gap-4 px-4 pt-4">
      <div className="flex items-center justify-between gap-3">
        <TopicMeta
          topics={vote.topics}
          short
          suffix={protocol ? t.protocol(protocol) : null}
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
          <h3 className={SECTION_LABEL}>{t.whatAbout}</h3>
          <p className="mt-1 text-[15px] leading-relaxed">{about}</p>
        </section>
      )}
      <section className="flex flex-col gap-1">
        <h3 className={SECTION_LABEL}>{t.howGroupsVoted}</h3>
        <PartyVoteTable vote={vote} />
      </section>
      <p className={cn('text-[13px]', MUTED_TEXT)}>
        {t.originalTitle(vote.title)}
      </p>
      {vote.citation_url && (
        <SourceLink href={vote.citation_url}>{t.voteOnAw}</SourceLink>
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

/**
 * The opened item: a little more than its card, then straight to the chat.
 * Full screen on phones, a centred column from md up.
 */
export function DailyDetailDialog({ item, heat, onClose }: Props) {
  const { t, intl, locale } = useFeedLocale();
  const context = item
    ? `${item.kind === 'vote' ? t.vote : t.plenarySitting} · ${longDayFormat(intl).format(new Date(`${item.digest.date}T00:00:00Z`))}`
    : '';

  return (
    <DialogPrimitive.Root
      open={item !== null}
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <DialogPrimitive.Content
          lang={locale}
          className={cn(
            DAILY_THEME_CLASSES,
            'fixed inset-0 z-50 flex flex-col bg-[var(--daily-canvas)] focus:outline-none md:inset-auto md:left-1/2 md:top-1/2 md:h-[90dvh] md:w-full md:max-w-screen-sm md:-translate-x-1/2 md:-translate-y-1/2 md:overflow-hidden md:rounded-xl',
          )}
        >
          {item && (
            <>
              <header className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--daily-border)] px-2 py-1.5">
                <DialogPrimitive.Close
                  aria-label={t.backToFeed}
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
                  aria-label={t.share}
                  onClick={() => shareItem(item, t.linkCopied)}
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
