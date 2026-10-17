'use client';

import { buildFeed, feedLists, rankFeed } from '@/lib/daily/feed';
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
import type {
  DailyDigest,
  DigestParliamentId,
} from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { useEffect, useMemo, useState } from 'react';
import { MUTED_TEXT } from './card-styles';
import DailyDaySection from './daily-day-section';
import { AskPanel, DailyDetailDialog } from './daily-detail-dialog';
import { ParliamentSelector, TopicPills } from './daily-filters';

const ITEM_PARAM = 'item';

type Props = {
  digests: Record<DigestParliamentId, DailyDigest[]>;
  /** Local dev previews, see `lib/daily/local-preview.ts`. */
  previewDigests?: DailyDigest[];
  /** From the URL; `undefined` lets the stored choice decide. */
  initialStates: StateSelection | undefined;
  initialTopics: string[];
  initialItem: string | undefined;
};

/** Mirror the view into the URL without a server round-trip, so a shared
 * link reproduces it, down to an opened item. */
function syncUrl(
  states: StateSelection,
  topics: string[],
  item: string | null,
) {
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

function DailyFeed({
  digests,
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

  // A link's land param wins; otherwise restore this device's last choice.
  useEffect(() => {
    if (initialStates === undefined) {
      setStates(storedStates());
    }
  }, [initialStates]);

  const lists = useMemo(
    () => feedLists(digests, parliamentsFor(states), previewDigests),
    [digests, previewDigests, states],
  );
  const days = useMemo(
    () => rankFeed(buildFeed(lists), topics),
    [lists, topics],
  );

  const allDigests = useMemo(() => lists.flat(), [lists]);
  const openItem = openKey ? (findItem(allDigests, openKey) ?? null) : null;
  const openHeat = days
    .map((d) => (openKey ? d.heat.get(openKey) : undefined))
    .find((h) => h !== undefined);

  const inViewKey = useItemInView(days);
  const askItem: DetailItem | null =
    (inViewKey && findItem(allDigests, inViewKey)) ||
    days.find((d) => d.hot)?.hot ||
    null;

  const changeStates = (next: StateSelection) => {
    setStates(next);
    storeStates(next);
    syncUrl(next, topics, openKey);
  };
  const changeTopics = (next: string[]) => {
    setTopics(next);
    syncUrl(states, next, openKey);
  };
  const open = (key: string | null) => {
    setOpenKey(key);
    syncUrl(states, topics, key);
  };

  return (
    <div className="flex flex-col gap-4 pt-4">
      <ParliamentSelector states={states} onChange={changeStates} />
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
