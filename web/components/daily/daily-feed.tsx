'use client';

import type { Locale } from '@/i18n/locales';
import { feedToDigests } from '@/lib/daily/editions';
import {
  buildFeed,
  feedLists,
  rankFeed,
  windowedDigests,
} from '@/lib/daily/feed';
import { type DetailItem, findItem } from '@/lib/daily/items';
import {
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
} from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useMemo, useState } from 'react';
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

function digestsOf(pages: FeedPage[], locale: Locale): DailyDigest[] {
  return feedToDigests(
    {
      editions: pages.flatMap((p) => p.editions),
      items: pages.flatMap((p) => p.items),
    },
    locale,
  );
}

function digestsIn(
  pages: Pages,
  locale: Locale,
): Record<DigestParliamentId, DailyDigest[]> {
  return {
    bundestag: digestsOf(pages.bundestag, locale),
    landtag_st: digestsOf(pages.landtag_st, locale),
    landtag_bw: digestsOf(pages.landtag_bw, locale),
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

  // A link's land param wins; otherwise restore this device's last choice.
  useEffect(() => {
    if (initialStates === undefined) {
      setStates(storedStates());
    }
  }, [initialStates]);

  // Both languages are loaded with the feed; the page's locale picks one.
  const locale = useLocale();
  const t = useTranslations('feed');
  const digests = useMemo(() => digestsIn(pages, locale), [pages, locale]);
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

  const loadOlder = async () => {
    setLoadingOlder(true);
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
      toast.error(t('olderFailed'));
    } finally {
      setLoadingOlder(false);
    }
  };

  const allDigests = useMemo(() => lists.flat(), [lists]);
  const openItem = openKey ? (findItem(allDigests, openKey) ?? null) : null;
  // An old link may name the item by a legacy key; heat is keyed by its id.
  const openHeat = days
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
      <ParliamentSelector states={states} onChange={changeStates} />
      <TopicPills topics={topics} onChange={changeTopics} />

      <div className="flex flex-col gap-12 pt-2">
        {days.length === 0 ? (
          <p className={cn('py-12 text-center text-[15px]', MUTED_TEXT)}>
            {t('empty')}
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
          <button
            type="button"
            onClick={loadOlder}
            disabled={loadingOlder}
            className={cn(
              'mx-auto h-10 rounded-lg border border-[var(--daily-border)] px-4 text-[15px] transition-colors hover:bg-[var(--daily-surface)] disabled:opacity-60',
              MUTED_TEXT,
              FOCUS_RING,
            )}
          >
            {loadingOlder ? t('loadingOlder') : t('olderDays')}
          </button>
        )}
      </div>

      {askItem && (
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
