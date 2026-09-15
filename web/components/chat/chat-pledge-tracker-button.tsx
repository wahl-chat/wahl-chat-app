'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { BorderTrail } from '@/components/ui/border-trail';
import {
  formatPledgeDate,
  getVisiblePledges,
  sortedRelevantEvents,
} from '@/lib/pledge-tracker/pledges';
import type { StreamingMessage } from '@/lib/socket.types';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import { track } from '@vercel/analytics/react';
import { ChevronRight, Target } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

type Props = {
  partyId: string;
  message: MessageItem | StreamingMessage;
  revealed?: boolean;
  onToggle?: () => void;
  isLastMessage?: boolean;
};

// Per-session flag (resets each browser session) so the circling green glow
// draws attention until the user opens PledgeTracker once, then calms down.
const PLEDGE_TRACKER_OPENED_KEY = 'wahlchat.pledgeTrackerOpened';

// Real-exposure impression: fired once per message when the card is >=50%
// visible for a dwell period (IntersectionObserver), deduped across reloads
// via sessionStorage. Mount alone is NOT exposure — reloads rehydrate history,
// group-chat carousels render every slide into the DOM, and far-off-screen
// messages mount too, all of which would inflate the CTR denominator.
const IMPRESSION_KEY_PREFIX = 'wahlchat.ptImpression.';
const IMPRESSION_DWELL_MS = 1000;

function ChatPledgeTrackerButton({
  partyId,
  message,
  revealed,
  onToggle,
  isLastMessage,
}: Props) {
  const [neverOpened, setNeverOpened] = useState(false);

  // Only the newest answer glows, like the other action buttons: every pledge
  // card in the scrollback glowing at once reads as an error, and clicking one
  // would visibly calm only that card until the next render.
  const showGlow = Boolean(isLastMessage) && neverOpened;

  // The trigger IS the pledge card (design review): the first matched
  // pledge's claim — the popup card without its date/source line.
  const visiblePledges = getVisiblePledges(message.pledge_tracker);
  const claim = visiblePledges[0]?.claim;
  const pledges = visiblePledges.length;

  // Meta line: how much evidence backs the first pledge, how recent it is, and
  // whether further pledges matched — all already in the payload.
  const timeline = visiblePledges[0]
    ? sortedRelevantEvents(visiblePledges[0])
    : [];
  const latestDate = formatPledgeDate(timeline[0]?.date);
  const otherPledges = pledges - 1;
  const metaParts: string[] = [
    `${timeline.length} ${timeline.length === 1 ? 'Beleg' : 'Belege'}`,
  ];
  if (latestDate) {
    metaParts.push(`zuletzt ${latestDate}`);
  }
  if (otherPledges > 0) {
    metaParts.push(
      `+${otherPledges} ${otherPledges === 1 ? 'weiteres Ziel' : 'weitere Ziele'}`,
    );
  }

  useEffect(() => {
    try {
      setNeverOpened(
        window.sessionStorage.getItem(PLEDGE_TRACKER_OPENED_KEY) !== 'true',
      );
    } catch {
      setNeverOpened(false);
    }
  }, []);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const impressionFiredRef = useRef(false);
  const recordStudyEvent = useChatStore((state) => state.recordStudyEvent);

  // Claim the impression exactly once per message: sessionStorage dedupes
  // across reloads and re-mounts; the ref covers storage-less browsers.
  const claimImpression = useCallback(() => {
    if (impressionFiredRef.current) return;
    impressionFiredRef.current = true;
    try {
      const key = IMPRESSION_KEY_PREFIX + message.id;
      if (window.sessionStorage.getItem(key) === 'true') return;
      window.sessionStorage.setItem(key, 'true');
    } catch {
      // Storage unavailable: the ref still dedupes within this page load.
    }
    track('pledge_tracker_impression', {
      party: partyId,
      message_id: message.id,
      pledges,
    });
    // Study exposure log (no-op for non-participants): the researchers need
    // per-participant "treated vs merely assigned" — this is that signal.
    void recordStudyEvent('pledge_shown');
  }, [message.id, partyId, pledges, recordStudyEvent]);

  // Exposure = >=50% visible held for the dwell period. An inactive carousel
  // slide or an off-screen message reports ratio 0 (CarouselContent clips
  // with overflow-hidden), so no carousel-specific handling is needed.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    let timer: number | null = null;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[entries.length - 1];
        if (entry.intersectionRatio >= 0.5) {
          timer ??= window.setTimeout(() => {
            claimImpression();
            observer.disconnect();
          }, IMPRESSION_DWELL_MS);
        } else if (timer !== null) {
          window.clearTimeout(timer);
          timer = null;
        }
      },
      { threshold: [0, 0.5] },
    );
    observer.observe(el);
    return () => {
      if (timer !== null) window.clearTimeout(timer);
      observer.disconnect();
    };
  }, [claimImpression]);

  const handleClick = () => {
    // A click inside the dwell window still counts as an impression first —
    // otherwise CTR could exceed 100%.
    claimImpression();
    track('pledge_tracker_button_clicked', {
      party: partyId,
      message_id: message.id,
      pledges,
    });
    setNeverOpened(false);
    try {
      window.sessionStorage.setItem(PLEDGE_TRACKER_OPENED_KEY, 'true');
    } catch {
      // Ignore storage failures; the toggle should still work.
    }
    onToggle?.();
  };

  return (
    <div ref={containerRef} className="relative basis-full rounded-xl">
      <button
        type="button"
        aria-label={claim ? `PledgeTracker: ${claim}` : 'PledgeTracker'}
        aria-haspopup="dialog"
        aria-expanded={revealed}
        onClick={handleClick}
        className="group w-full rounded-xl border border-border/60 bg-muted/30 p-3 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        <span className="flex flex-col gap-2">
          {/* PledgeTracker mark instead of the party tile: the party logo
              already sits next to the answer, so a second one reads doubled.
              A target, not a check mark — a ticked box next to a party's claim
              would read as "fulfilled", the one verdict this feature never gives. */}
          <span className="flex items-center gap-2">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-md ring-1 ring-emerald-500/30">
              <Target
                aria-hidden
                className="size-4 text-emerald-600 dark:text-emerald-400"
              />
            </span>
            <span className="min-w-0 truncate text-xs font-medium text-emerald-600 dark:text-emerald-400">
              PledgeTracker
              <span className="font-normal text-muted-foreground">
                {' · Ziele im Verlauf'}
              </span>
            </span>
          </span>

          {/* Quoted: the claim is the party's own wording, not wahl.chat's. It
              spans the full card width because the CTA sits below it, so no
              line is cut short by a neighbouring element. */}
          <span className="line-clamp-2 text-[15px] font-semibold leading-snug text-foreground">
            {claim ? `„${claim}“` : 'Passende Ziele der Partei'}
          </span>

          <span className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {/* Volume and recency of the evidence: without it the card asks for
                a tap without saying what is behind it. nowrap (not truncate) so
                a tight screen wraps the CTA to its own line instead of cutting
                the date in half. */}
            <span className="whitespace-nowrap text-xs text-muted-foreground">
              {metaParts.join(' · ')}
            </span>
            {/* CTA affordance: looks like a button, but the whole card is the
                real <button> — a nested interactive element would be invalid. */}
            <span className="ml-auto inline-flex shrink-0 items-center gap-1 rounded-md border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground shadow-sm group-hover:bg-accent">
              Umsetzung ansehen
              <ChevronRight aria-hidden className="size-3.5" />
            </span>
          </span>
        </span>
      </button>
      {showGlow && (
        <>
          {/* Pill-era BorderTrail, scaled up: the card's perimeter is much
              longer than the old button's, so the streak (size) and the green
              bloom are enlarged to read at this width. */}
          <BorderTrail
            className="bg-emerald-300/40"
            size={160}
            style={{
              boxShadow:
                '0px 0px 80px 40px rgb(110 231 183 / 55%), 0 0 120px 70px rgb(0 0 0 / 50%), 0 0 160px 100px rgb(0 0 0 / 50%)',
            }}
          />
        </>
      )}
    </div>
  );
}

export default ChatPledgeTrackerButton;
