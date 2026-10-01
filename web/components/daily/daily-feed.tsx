'use client';

import Logo from '@/components/chat/logo';
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
import { CARD_PLACEHOLDER, INK_LABEL, MUTED_TEXT } from './card-styles';
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

/** Playful sticker beside the page title, so the brand is visible on the
 * feed without a hero. */
function PresentedBy() {
  return (
    <span className="inline-flex -rotate-3 items-center gap-2 rounded-[4px] border-2 border-[var(--daily-ink)] bg-[var(--daily-surface)] px-2.5 py-1 shadow-[3px_3px_0_0_var(--daily-ink)]">
      <span className="font-display text-sm font-bold italic">
        präsentiert von
      </span>
      <Logo variant="small" className="size-5 text-[var(--daily-ink)]" />
      <span className="font-display text-base font-black tracking-tight">
        wahl.chat
      </span>
    </span>
  );
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
    <div className="flex flex-col gap-10 pt-8">
      <DailyWaitlistCta state={state} />

      <header className="flex flex-col gap-3 pt-2">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
          <h1
            className={cn(
              INK_LABEL,
              'px-3 py-1.5 text-lg tracking-[0.16em] md:px-4 md:py-2 md:text-2xl',
            )}
          >
            Dein Parlament kompakt
          </h1>
          <PresentedBy />
        </div>
        <p className={cn('max-w-2xl text-base', MUTED_TEXT)}>
          Abstimmungen und Debatten aus Bundestag und Landtag. Tippe auf eine
          Karte für mehr Details und Quellen.
        </p>
      </header>

      <DailyFilters
        state={state}
        onStateChange={changeState}
        topics={topics}
        onTopicsChange={changeTopics}
      />

      {dayViews.length === 0 ? (
        <p className={cn(CARD_PLACEHOLDER, 'p-6 text-center text-sm')}>
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
