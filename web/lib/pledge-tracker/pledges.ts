import type {
  PledgeRecord,
  PledgeTimelineEvent,
  PledgeTrackerSuggestions,
} from '@/lib/stores/chat-store.types';
import { formatGermanDate } from '@/lib/utils';

/**
 * Only events PledgeTracker flagged as relevant for tracking (Cambridge label
 * "Ja") are shown. Context-only events are dropped entirely — the timeline
 * shows evidence, not the full crawl.
 */
export function relevantTimelineEvents(
  pledge: PledgeRecord,
): PledgeTimelineEvent[] {
  return (pledge.timeline_events ?? []).filter(
    (event) => event.is_relevant_for_tracking === true,
  );
}

/**
 * Relevant events, newest first. ISO date strings sort lexicographically, so a
 * plain string compare is also a chronological one; undated events sink last.
 */
export function sortedRelevantEvents(
  pledge: PledgeRecord,
): PledgeTimelineEvent[] {
  return relevantTimelineEvents(pledge).sort((a, b) =>
    (b.date ?? '').localeCompare(a.date ?? ''),
  );
}

/**
 * Pledges worth showing: those with at least one relevant event. A pledge
 * whose every event was context-only would open onto an empty timeline, so it
 * is hidden — including from the trigger button.
 */
export function getVisiblePledges(
  suggestions?: PledgeTrackerSuggestions | null,
): PledgeRecord[] {
  return (suggestions?.pledges ?? []).filter(
    (pledge) => relevantTimelineEvents(pledge).length > 0,
  );
}

/**
 * Format a PledgeTracker date for display. Source values are not always clean
 * ISO dates (e.g. "2026-06-18_19-48-08", "2023-06-01 (2025-08-13)"), so take
 * the leading date part and fall back to the raw string when it will not
 * parse.
 */
export function formatPledgeDate(value?: string | null): string | null {
  if (!value) {
    return null;
  }
  const isoPart = value.slice(0, 10);
  const parsed = new Date(isoPart);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return formatGermanDate(isoPart, 'medium') ?? value;
}
