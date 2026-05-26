'use client';

import { useEffect, useState } from 'react';

import type { LeafCloseInfo } from '@/modules/guided-exploration/hooks/use-leaf-close-flow';

interface LeafCloseAnnouncerProps {
  info: LeafCloseInfo | null;
}

/** Delay after the card is focused before pushing the announcement, so the
 *  card's focus read is spoken first and the announcement queues behind it
 *  rather than being preempted. Tunable per screen reader. */
const ANNOUNCE_DELAY_MS = 250;
/** Safety cap on how long we wait for the closing Sheet to leave the DOM
 *  (~640ms at 60fps) before giving up on the focus move. */
const MAX_WAIT_FRAMES = 40;

/**
 * Post-close feedback for the leaf sidebar. Returns focus to the leaf card the
 * user was just in (a real <button> with a terse "{name}, {status}" label, so
 * landing on it reads the topic and its updated status), then — a beat later —
 * announces what just happened ("Als erkundet markiert. …") via a polite live
 * region.
 *
 * Timing is the whole game here:
 *  - We must wait for the leaf Sheet to actually unmount. It animates out over
 *    200ms, and while it lingers its focus scope keeps yanking focus back to
 *    its own content (whose title reads "Thema"). Focusing the card during
 *    that window loses the race — the user lands on the dying Sheet, not the
 *    card. So we poll per frame until no dialog is in the DOM, then focus once.
 *  - We announce *after* the focus read, so the polite region queues behind it
 *    instead of being preempted by it (the old order let focus kill the
 *    announcement, so it was never heard).
 *
 * Lives in the parent because the sidebar — and its own live region — unmount
 * on close.
 */
export function LeafCloseAnnouncer({ info }: LeafCloseAnnouncerProps) {
  const focusLeafId = info?.focusLeafId;
  const announcement = info?.announcement ?? '';
  const [liveText, setLiveText] = useState('');

  useEffect(() => {
    if (!focusLeafId) return;
    // Clear first so an identical announcement (e.g. closing the same leaf
    // twice) is still seen as a change and re-announced.
    setLiveText('');

    let frame = 0;
    let raf = 0;
    let announceTimer = 0;
    const focusWhenSheetGone = () => {
      frame += 1;
      // The Sheet (role="dialog") still owns focus until it unmounts.
      if (!document.querySelector('[role="dialog"]')) {
        document.getElementById(`leaf-card-${focusLeafId}`)?.focus();
        announceTimer = window.setTimeout(
          () => setLiveText(announcement),
          ANNOUNCE_DELAY_MS,
        );
        return;
      }
      if (frame < MAX_WAIT_FRAMES) {
        raf = requestAnimationFrame(focusWhenSheetGone);
      }
    };
    raf = requestAnimationFrame(focusWhenSheetGone);

    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(announceTimer);
    };
    // key changes on every close, including repeat closes of the same leaf.
  }, [info?.key, focusLeafId, announcement]);

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"
    >
      {liveText}
    </div>
  );
}
