'use client';

import { buildFeed } from '@/lib/daily/feed';
import {
  STATE_PARAM,
  type StateSelection,
  parliamentsFor,
} from '@/lib/daily/region';
import { TOPICS_PARAM } from '@/lib/daily/topics';
import type {
  DailyDigest,
  DigestParliamentId,
} from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { useCallback, useMemo, useState } from 'react';
import { CARD_PLACEHOLDER } from './card-styles';
import DailyDaySection from './daily-day-section';
import { DailyDetailDialog } from './daily-detail-dialog';
import DailyFilters from './daily-filters';
import DailyWaitlistCta from './daily-waitlist-cta';
import { detailItems, viewDay } from './detail-items';

type Props = {
  digests: Record<DigestParliamentId, DailyDigest[]>;
  initialState: StateSelection;
  initialTopics: string[];
};

/** Mirror the filters into the URL without a server round-trip, so a
 * shared link reproduces the view. */
function syncUrl(state: StateSelection, topics: string[]) {
  const url = new URL(window.location.href);
  url.searchParams.set(STATE_PARAM, state.toLowerCase());
  if (topics.length > 0) {
    url.searchParams.set(TOPICS_PARAM, topics.join(','));
  } else {
    url.searchParams.delete(TOPICS_PARAM);
  }
  window.history.replaceState(null, '', url);
}

function DailyFeed({ digests, initialState, initialTopics }: Props) {
  const [state, setState] = useState(initialState);
  const [topics, setTopics] = useState(initialTopics);
  const [open, setOpen] = useState<{ date: string; index: number } | null>(
    null,
  );

  const days = useMemo(
    () => buildFeed(parliamentsFor(state).map((p) => digests[p])),
    [digests, state],
  );
  const dayViews = useMemo(
    () =>
      days.map((day) => {
        const views = viewDay(day, topics);
        return { day, views, items: detailItems(views) };
      }),
    [days, topics],
  );
  const openDay = dayViews.find((d) => d.day.date === open?.date);

  const changeState = (next: StateSelection) => {
    setState(next);
    setOpen(null);
    syncUrl(next, topics);
  };
  const changeTopics = (next: string[]) => {
    setTopics(next);
    setOpen(null);
    syncUrl(state, next);
  };
  const changeIndex = useCallback(
    (index: number | null) =>
      setOpen((current) =>
        current && index !== null ? { ...current, index } : null,
      ),
    [],
  );

  return (
    <div className="flex flex-col gap-6 pt-6">
      <DailyWaitlistCta state={state} />

      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold">Was im Parlament passiert ist</h1>
        <p className="text-sm text-muted-foreground">
          Abstimmungen und Debatten der letzten zwei Wochen aus Bundestag und
          Landtag. Tippe auf eine Karte für Details und Quellen.
        </p>
      </header>

      <DailyFilters
        state={state}
        onStateChange={changeState}
        topics={topics}
        onTopicsChange={changeTopics}
      />

      {dayViews.length === 0 ? (
        <p
          className={cn(
            CARD_PLACEHOLDER,
            'p-6 text-center text-sm text-muted-foreground',
          )}
        >
          Noch keine Inhalte verfügbar. Schau bald wieder vorbei.
        </p>
      ) : (
        dayViews.map(({ day, views, items }) => (
          <DailyDaySection
            key={day.date}
            day={day}
            views={views}
            items={items}
            selectedTopics={topics}
            onOpen={(index) => setOpen({ date: day.date, index })}
          />
        ))
      )}

      <DailyDetailDialog
        items={openDay?.items ?? []}
        index={openDay ? (open?.index ?? null) : null}
        selectedTopics={topics}
        onIndexChange={changeIndex}
      />
    </div>
  );
}

export default DailyFeed;
