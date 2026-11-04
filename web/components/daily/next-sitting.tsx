'use client';

import {
  berlinToday,
  nextSitting,
  nextSittingText,
} from '@/lib/daily/next-sitting';
import type { SittingCalendar } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { FOCUS_RING, META_TEXT } from './card-styles';

const AGENDA_URL = 'https://www.bundestag.de/tagesordnung';

/** One quiet line on when the Bundestag sits next, so a feed that has not
 * moved for a while reads as a recess rather than as stale. */
function NextSitting({ calendar }: { calendar: SittingCalendar | null }) {
  // Fixed at first render: the server renders per request, so it only differs
  // from the browser's day across midnight.
  const [today] = useState(berlinToday);
  const next = nextSitting(calendar, today);
  if (!next) {
    return null;
  }
  return (
    <p className={META_TEXT} suppressHydrationWarning>
      {nextSittingText(next, today)}{' '}
      <a
        href={AGENDA_URL}
        target="_blank"
        rel="noopener noreferrer"
        className={cn('underline underline-offset-2', FOCUS_RING)}
      >
        Tagesordnung
      </a>
    </p>
  );
}

export default NextSitting;
