'use client';

import { FEED_CHAT_ENABLED } from '@/lib/daily/chat-handoff';
import { feedToDigests } from '@/lib/daily/editions';
import {
  buildFeed,
  feedLists,
  rankFeed,
  windowedDigests,
} from '@/lib/daily/feed';
import { type DetailItem, findItem } from '@/lib/daily/items';
import {
  BUNDESTAG,
  DEFAULT_SELECTION,
  STATE_PARAM,
  STATE_STORAGE_KEY,
  type StateSelection,
  parliamentsFor,
  parseStateParam,
} from '@/lib/daily/region';
import { TOPICS_PARAM } from '@/lib/daily/topics';
import { getOlderParliamentFeed } from '@/lib/firebase/firebase-server';
import type {
  DailyDigest,
  DigestParliamentId,
  FeedPage,
  ParliamentFeed,
  SittingCalendar,
} from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { FOCUS_RING, MUTED_TEXT } from './card-styles';
import DailyDaySection from './daily-day-section';
import { AskPanel, DailyDetailDialog } from './daily-detail-dialog';
import { ParliamentSelector, TopicPills } from './daily-filters';

const ITEM_PARAM = 'item';

type Pages = Record<DigestParliamentId, FeedPage[]>;

type Props = {
  /** Each parliament's latest slice; older ones load on request. */
  feeds: Record<DigestParliamentId, FeedPage>;
  /** Local dev previews, see `lib/daily/local-preview.ts`. */
  previewDigests?: DailyDigest[];
  /** From the URL; `undefined` lets the stored choice decide. */
  initialStates: StateSelection | undefined;
  initialTopics: string[];
  initialItem: string | undefined;
  /** The day of a shared item, which may be older than the first slice. */
  linkedDay?: ParliamentFeed | null;
  /** The Bundestag's sitting weeks, for the parliament field. */
  calendar?: SittingCalendar | null;
  /** The days the Bundestag's feed has content for. */
  editionDates?: string[];
};

type View = {
  states: StateSelection;
  topics: string[];
  item: string | null;
};

/** Mirror the view into the URL without a server round-trip, so a shared
 * link reproduces it, down to an opened item. */
function syncUrl({ states, topics, item }: View) {
  const url = new URL(window.location.href);
  const set = (key: string, value: string | null) =>
    value ? url.searchParams.set(key, value) : url.searchParams.delete(key);
  set(STATE_PARAM, states.join(',').toLowerCase() || null);
  set(TOPICS_PARAM, topics.join(',') || null);
  set(ITEM_PARAM, item);
  window.history.replaceState(null, '', url);
}

function storedStates(): StateSelection {
  try {
    return (
      parseStateParam(window.localStorage.getItem(STATE_STORAGE_KEY)) ??
      DEFAULT_SELECTION
    );
  } catch {
    return DEFAULT_SELECTION;
  }
}

function storeStates(states: StateSelection) {
  try {
    window.localStorage.setItem(STATE_STORAGE_KEY, states.join(','));
  } catch {
    // Storage blocked: the choice still holds for this visit via the URL.
  }
}

/** The card most in view, so the floating input asks about what is read. */
function useItemInView(deps: unknown): string | null {
  const [key, setKey] = useState<string | null>(null);
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.find((e) => e.isIntersecting);
        if (visible) {
          setKey((visible.target as HTMLElement).dataset.itemKey ?? null);
        }
      },
      { rootMargin: '-40% 0px -40% 0px' },
    );
    for (const el of document.querySelectorAll('[data-item-key]')) {
      observer.observe(el);
    }
    return () => observer.disconnect();
  }, [deps]);
  return key;
}

/**
 * Calls `onReach` while the returned element is near the viewport. The
 * observer is rebuilt on every `deps` change, and a fresh observer reports at
 * once, so a slice too short to fill the screen (a recess) chains straight
 * into the next load.
 */
function useNearViewport(onReach: () => void, enabled: boolean, deps: unknown) {
  const ref = useRef<HTMLDivElement>(null);
  const onReachRef = useRef(onReach);
  useEffect(() => {
    onReachRef.current = onReach;
  });
  useEffect(() => {
    const el = ref.current;
    if (!enabled || !el) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          onReachRef.current();
        }
      },
      { rootMargin: '600px 0px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [enabled, deps]);
  return ref;
}

function digestsOf(pages: FeedPage[]): DailyDigest[] {
  return feedToDigests({
    editions: pages.flatMap((p) => p.editions),
    items: pages.flatMap((p) => p.items),
  });
}

function digestsIn(pages: Pages): Record<DigestParliamentId, DailyDigest[]> {
  return {
    bundestag: digestsOf(pages.bundestag),
    landtag_st: digestsOf(pages.landtag_st),
    landtag_bw: digestsOf(pages.landtag_bw),
  };
}

/** The selected parliaments that have an older slice, with its cursor. */
function olderCursors(
  pages: Pages,
  parliaments: readonly DigestParliamentId[],
): [DigestParliamentId, string][] {
  return parliaments.flatMap((parliament) => {
    const last = pages[parliament].at(-1);
    return last?.hasOlder && last.from ? [[parliament, last.from]] : [];
  }) as [DigestParliamentId, string][];
}

function DailyFeed({
  feeds,
  previewDigests,
  initialStates,
  initialTopics,
  initialItem,
  linkedDay,
  calendar = null,
  editionDates = [],
}: Props) {
  const [states, setStates] = useState<StateSelection>(
    initialStates ?? DEFAULT_SELECTION,
  );
  const [topics, setTopics] = useState(initialTopics);
  const [openKey, setOpenKey] = useState<string | null>(initialItem ?? null);
  const [pages, setPages] = useState<Pages>(() => ({
    bundestag: [feeds.bundestag],
    landtag_st: [feeds.landtag_st],
    landtag_bw: [feeds.landtag_bw],
  }));
  const [loadingOlder, setLoadingOlder] = useState(false);
  // Stops loading on scroll after a failure; a click retries.
  const [olderFailed, setOlderFailed] = useState(false);
  // Set synchronously, unlike state: the observer can report twice before a
  // render, and a calendar jump rebuilds the pages from a snapshot that a
  // concurrent load would duplicate.
  const busy = useRef(false);
  // A day chosen in the calendar, scrolled to once it is rendered.
  const [jumpTarget, setJumpTarget] = useState<string | null>(null);

  // A link's land param wins; otherwise restore this device's last choice.
  useEffect(() => {
    if (initialStates === undefined) {
      setStates(storedStates());
    }
  }, [initialStates]);

  const digests = useMemo(() => digestsIn(pages), [pages]);
  // The server already cut the stored slices; only previews need a window.
  const lists = useMemo(
    () =>
      feedLists(
        digests,
        parliamentsFor(states),
        windowedDigests(previewDigests ?? []),
      ),
    [digests, previewDigests, states],
  );
  const days = useMemo(
    () => rankFeed(buildFeed(lists, null), topics),
    [lists, topics],
  );
  const older = olderCursors(pages, parliamentsFor(states));

  useEffect(() => {
    if (!jumpTarget) {
      return;
    }
    const section = document.getElementById(`tag-${jumpTarget}`);
    if (section) {
      section.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Keyboard and screen reader users land on the day too.
      section.focus({ preventScroll: true });
      setJumpTarget(null);
    } else if (topics.length > 0) {
      // A topic filter hides the day; it is back on the next render.
      setTopics([]);
      syncUrl({ states, topics: [], item: openKey });
    } else {
      setJumpTarget(null);
    }
  }, [jumpTarget, days, topics, states, openKey]);

  const loadOlder = async () => {
    if (busy.current) {
      return;
    }
    busy.current = true;
    setLoadingOlder(true);
    setOlderFailed(false);
    try {
      const loaded = await Promise.all(
        older.map(([parliament, from]) =>
          getOlderParliamentFeed(parliament, from),
        ),
      );
      setPages((current) => {
        const next = { ...current };
        older.forEach(([parliament], i) => {
          next[parliament] = [...current[parliament], loaded[i]];
        });
        return next;
      });
    } catch {
      toast.error('Ältere Tage konnten nicht geladen werden.');
      setOlderFailed(true);
    } finally {
      busy.current = false;
      setLoadingOlder(false);
    }
  };
  const olderRef = useNearViewport(
    loadOlder,
    older.length > 0 && !olderFailed,
    pages,
  );

  const allDigests = useMemo(() => lists.flat(), [lists]);
  // Only for opening a shared item the loaded slices do not reach; the feed
  // itself never shows it out of order.
  const linkedDigests = useMemo(
    () => (linkedDay ? feedToDigests(linkedDay) : []),
    [linkedDay],
  );
  const openItem = openKey
    ? (findItem(allDigests, openKey) ??
      findItem(linkedDigests, openKey) ??
      null)
    : null;
  // A linked item may lie outside the loaded days; its heat is then ranked
  // within its own day.
  const openHeat = [...days, ...rankFeed(buildFeed([linkedDigests], null), [])]
    .map((d) => (openItem ? d.heat.get(openItem.key) : undefined))
    .find((h) => h !== undefined);

  const inViewKey = useItemInView(days);
  const askItem: DetailItem | null =
    (inViewKey && findItem(allDigests, inViewKey)) ||
    days.find((d) => d.hot)?.hot ||
    null;

  const view: View = { states, topics, item: openKey };
  const changeStates = (next: StateSelection) => {
    setStates(next);
    storeStates(next);
    syncUrl({ ...view, states: next });
  };
  /** Show a sitting day from the calendar: load older slices until one
   * holds it, select the Bundestag and lift a topic filter if either hides
   * it, then scroll to it. */
  const jumpToDay = async (date: string) => {
    if (busy.current) {
      toast.info('Einen Moment, ältere Tage werden noch geladen.');
      return;
    }
    busy.current = true;
    const loaded = [...pages.bundestag];
    try {
      for (
        let last = loaded.at(-1);
        last?.from && last.hasOlder && date < last.from;
        last = loaded.at(-1)
      ) {
        loaded.push(await getOlderParliamentFeed('bundestag', last.from));
      }
    } catch {
      toast.error('Dieser Tag konnte nicht geladen werden.');
      return;
    } finally {
      busy.current = false;
    }
    setPages((current) => ({ ...current, bundestag: loaded }));
    if (!states.includes(BUNDESTAG)) {
      changeStates([BUNDESTAG, ...states]);
    }
    setJumpTarget(date);
  };

  const changeTopics = (next: string[]) => {
    setTopics(next);
    syncUrl({ ...view, topics: next });
  };
  const open = (key: string | null) => {
    setOpenKey(key);
    syncUrl({ ...view, item: key });
  };

  return (
    <div className="flex flex-col gap-4 pt-4">
      <ParliamentSelector
        states={states}
        onChange={changeStates}
        calendar={calendar}
        editionDates={editionDates}
        onJumpToDay={jumpToDay}
      />
      <TopicPills topics={topics} onChange={changeTopics} />

      <div className="flex flex-col gap-12 pt-2">
        {days.length === 0 ? (
          <p className={cn('py-12 text-center text-[15px]', MUTED_TEXT)}>
            Noch keine Inhalte zu deiner Auswahl. Schau bald wieder vorbei.
          </p>
        ) : (
          days.map((day) => (
            <DailyDaySection
              key={day.date}
              day={day}
              onOpen={(item) => open(item.key)}
            />
          ))
        )}
        {older.length > 0 && (
          <div
            ref={olderRef}
            aria-live="polite"
            className="flex min-h-10 items-center justify-center"
          >
            {olderFailed ? (
              <button
                type="button"
                onClick={loadOlder}
                className={cn(
                  'h-10 rounded-lg border border-[var(--daily-border)] px-4 text-[15px] transition-colors hover:bg-[var(--daily-surface)]',
                  MUTED_TEXT,
                  FOCUS_RING,
                )}
              >
                Erneut versuchen
              </button>
            ) : (
              loadingOlder && (
                <span className={cn('text-[15px]', MUTED_TEXT)}>
                  Ältere Tage laden …
                </span>
              )
            )}
          </div>
        )}
      </div>

      {FEED_CHAT_ENABLED && askItem && (
        <AskPanel
          item={askItem}
          withSuggestions={false}
          className="sticky bottom-0 z-30 -mx-2 mt-4"
        />
      )}

      <DailyDetailDialog
        item={openItem}
        heat={openHeat}
        onClose={() => open(null)}
      />
    </div>
  );
}

export default DailyFeed;
