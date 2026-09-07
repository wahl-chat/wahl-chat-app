'use client';

import { ChatMessageIcon } from '@/components/chat/chat-message-icon';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { PLEDGE_TRACKER_BRAND } from '@/lib/pledge-tracker/brand';
import {
  formatPledgeDate,
  getVisiblePledges,
  sortedRelevantEvents,
} from '@/lib/pledge-tracker/pledges';
import type {
  MessageItem,
  PledgeRecord,
  PledgeTimelineEvent,
} from '@/lib/stores/chat-store.types';
import { cn } from '@/lib/utils';
import { ChevronDown, ExternalLink, SquareCheckBig } from 'lucide-react';
import { useState } from 'react';

type Props = {
  message: MessageItem;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

/**
 * PledgeTracker popup: up to three pledges relevant to the conversation for
 * the answering party, each with a vertical timeline of dated, source-linked
 * events (University of Cambridge research data). Only events labelled
 * relevant for tracking are shown; the UI never claims a pledge was fulfilled
 * or broken.
 */
function ChatPledgeTracker({ message, open, onOpenChange }: Props) {
  const pledges = getVisiblePledges(message.pledge_tracker);
  const [selectedIndex, setSelectedIndex] = useState(0);

  if (pledges.length === 0) {
    return null;
  }

  const activeIndex = Math.min(selectedIndex, pledges.length - 1);
  const activePledge = pledges[activeIndex];
  const zielWord = pledges.length === 1 ? 'Ziel' : 'Ziele';
  const matchWord = pledges.length === 1 ? 'passendes' : 'passende';

  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      <ResponsiveDialogContent className="flex max-h-[95dvh] flex-col gap-0 p-0 md:max-w-xl">
        <ResponsiveDialogHeader className="shrink-0 space-y-0 border-b border-border px-5 py-4 text-left sm:text-left">
          <ResponsiveDialogTitle className="text-base">
            <span className="flex items-center gap-2.5">
              <SquareCheckBig className="size-5 shrink-0 text-emerald-500" />
              <a
                href={PLEDGE_TRACKER_BRAND.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 font-semibold underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                {PLEDGE_TRACKER_BRAND.name}
                <ExternalLink className="size-3.5 shrink-0 text-muted-foreground" />
              </a>
            </span>
          </ResponsiveDialogTitle>
          <ResponsiveDialogDescription className="sr-only">
            Zeitleisten zu politischen Zielen, erstellt von PledgeTracker.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        <div className="flex grow flex-col gap-4 overflow-y-auto px-5 py-4">
          <p className="text-xs text-muted-foreground">
            {pledges.length} {matchWord} {zielWord} zu diesem Gespräch
          </p>

          {pledges.length > 1 && (
            <div className="flex gap-1.5">
              {pledges.map((pledge, index) => (
                <button
                  key={pledge.pledge_id}
                  type="button"
                  aria-pressed={index === activeIndex}
                  onClick={() => setSelectedIndex(index)}
                  className={cn(
                    'min-w-0 flex-1 truncate rounded-md border px-2.5 py-1.5 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    index === activeIndex
                      ? 'border-emerald-500/40 bg-emerald-500/10 font-medium text-foreground'
                      : 'border-border text-muted-foreground hover:bg-accent/50',
                  )}
                >
                  {pledge.policy_area || `Ziel ${index + 1}`}
                </button>
              ))}
            </div>
          )}

          <PledgeSummaryCard pledge={activePledge} />

          {/* Keyed so expand/collapse state resets when switching pledges. */}
          <PledgeTimeline key={activePledge.pledge_id} pledge={activePledge} />

          <PledgeDisclaimer />
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

function PledgeSummaryCard({ pledge }: { pledge: PledgeRecord }) {
  const pledgeDate = formatPledgeDate(pledge.pledge_date);
  const sourceTitle = pledge.pledge_source_title ?? pledge.pledge_source_url;
  const statusLabel = pledge.tracker_status_label;

  return (
    <div className="rounded-xl border border-border/60 bg-muted/30 p-4">
      <div className="flex items-start gap-3">
        <ChatMessageIcon partyId={pledge.party_id} shape="tile" />
        <div className="flex min-w-0 flex-col gap-2">
          <p className="text-[15px] font-semibold leading-snug text-foreground">
            {pledge.claim}
          </p>

          {(pledgeDate || sourceTitle) && (
            <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-muted-foreground">
              {pledgeDate && <span>Ziel vom {pledgeDate}</span>}
              {pledgeDate && sourceTitle && (
                <span aria-hidden className="text-border">
                  ·
                </span>
              )}
              {sourceTitle &&
                (pledge.pledge_source_url ? (
                  <a
                    href={pledge.pledge_source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-w-0 items-center gap-1 underline underline-offset-2 hover:text-foreground"
                  >
                    <span className="truncate">{sourceTitle}</span>
                    <ExternalLink className="size-3 shrink-0" />
                  </a>
                ) : (
                  <span className="truncate">{sourceTitle}</span>
                ))}
            </p>
          )}

          {statusLabel && (
            <p className="text-xs text-muted-foreground">
              Status:{' '}
              <span className="font-medium text-foreground">
                {pledge.tracker_step
                  ? `${statusLabel}, ${pledge.tracker_step}`
                  : statusLabel}
              </span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// Collapse the timeline middle only when it hides at least 2 events: with
// >= 5 events we show newest, second-newest, an expander, and the oldest.
const COLLAPSE_MIN_EVENTS = 5;

function PledgeTimeline({ pledge }: { pledge: PledgeRecord }) {
  const [showAll, setShowAll] = useState(false);
  const events = sortedRelevantEvents(pledge);
  const isCollapsed = !showAll && events.length >= COLLAPSE_MIN_EVENTS;
  const hiddenCount = events.length - 3;

  const renderEvent = (event: PledgeTimelineEvent, index: number) => (
    <TimelineEvent
      key={`${event.date}-${event.url ?? index}`}
      event={event}
      isLast={index === events.length - 1}
      number={events.length - index}
      isNewest={index === 0}
    />
  );

  if (!isCollapsed) {
    return <ol className="relative">{events.map(renderEvent)}</ol>;
  }

  // "1, 2, …, N": two newest events, collapsed middle, oldest event.
  return (
    <ol className="relative">
      {events.slice(0, 2).map(renderEvent)}
      <li className="relative pb-6 pl-8">
        {/* Continuous spine through the collapsed gap. */}
        <span
          aria-hidden
          className="absolute inset-y-0 left-2 w-px bg-border"
        />
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronDown className="size-3.5 shrink-0" />
          {hiddenCount} weitere Ereignisse anzeigen
        </button>
      </li>
      {renderEvent(events[events.length - 1], events.length - 1)}
    </ol>
  );
}

function TimelineEvent({
  event,
  isLast,
  number,
  isNewest,
}: {
  event: PledgeTimelineEvent;
  isLast: boolean;
  /** Chronological position: 1 = oldest event, highest = newest (shown on top). */
  number: number;
  isNewest: boolean;
}) {
  const [showFullText, setShowFullText] = useState(false);
  const date = formatPledgeDate(event.date);
  const shortTitle = event.event_short?.trim();
  const hasShortTitle = Boolean(shortTitle) && shortTitle !== event.event;

  return (
    <li className={cn('relative pl-8', !isLast && 'pb-6')}>
      {/* Spine: drawn per item so the last event has no trailing line. */}
      {!isLast && (
        <span
          aria-hidden
          className="absolute bottom-0 left-2 top-5 w-px bg-border"
        />
      )}
      <span
        aria-hidden
        className={cn(
          'absolute left-0 top-0.5 flex size-4 items-center justify-center rounded-full border bg-background text-[10px] font-medium leading-none',
          isNewest
            ? 'border-emerald-500/50 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
            : 'border-border text-muted-foreground',
        )}
      >
        {number}
      </span>
      {isNewest && <span className="sr-only">Neuestes Ereignis</span>}

      {date && (
        <time className="text-xs font-medium text-muted-foreground">
          {date}
        </time>
      )}

      {hasShortTitle ? (
        <>
          <p className="mt-1 text-sm leading-relaxed text-foreground">
            {shortTitle}
          </p>
          {showFullText && (
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
              {event.event}
            </p>
          )}
        </>
      ) : (
        <p className="mt-1 text-sm leading-relaxed text-foreground">
          {event.event}
        </p>
      )}

      <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
        {hasShortTitle && (
          <button
            type="button"
            aria-expanded={showFullText}
            onClick={() => setShowFullText((v) => !v)}
            className="underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {showFullText ? 'Weniger' : 'Mehr'}
          </button>
        )}
        {event.url && (
          <a
            href={event.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 underline-offset-2 hover:text-foreground hover:underline"
          >
            Quelle
            <ExternalLink className="size-3 shrink-0" />
          </a>
        )}
      </div>
    </li>
  );
}

/**
 * Research-context note: one-line tagline with the details behind "Mehr" —
 * the AiDisclaimer pattern, expanded inline instead of nesting a second
 * dialog/drawer inside the popup.
 */
function PledgeDisclaimer() {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div className="mt-1 text-xs leading-relaxed text-muted-foreground">
      <p>
        {PLEDGE_TRACKER_BRAND.taglineText}{' '}
        <button
          type="button"
          aria-expanded={showDetails}
          onClick={() => setShowDetails((v) => !v)}
          className="font-medium underline underline-offset-2 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {showDetails ? 'Weniger' : 'Mehr'}
        </button>
      </p>
      {showDetails && <p className="mt-1">{PLEDGE_TRACKER_BRAND.detailText}</p>}
    </div>
  );
}

export default ChatPledgeTracker;
