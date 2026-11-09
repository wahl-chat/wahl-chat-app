import type {
  DigestParliamentId,
  FeedPage,
} from '@/lib/firebase/firebase.types';

/** Each parliament's loaded slices, newest first. */
export type Pages = Record<DigestParliamentId, FeedPage[]>;

export type OlderCursor = [DigestParliamentId, string];

/** The selected parliaments that have an older slice, with its cursor. */
export function olderCursors(
  pages: Pages,
  parliaments: readonly DigestParliamentId[],
): OlderCursor[] {
  return parliaments.flatMap((parliament): OlderCursor[] => {
    const last = pages[parliament].at(-1);
    return last?.hasOlder && last.from ? [[parliament, last.from]] : [];
  });
}

/** The pages with each loaded slice appended to its parliament. */
export function appendPages(
  pages: Pages,
  loaded: readonly (readonly [DigestParliamentId, FeedPage])[],
): Pages {
  const next = { ...pages };
  for (const [parliament, page] of loaded) {
    next[parliament] = [...next[parliament], page];
  }
  return next;
}

/** One request per slice: the key a prefetched slice is kept under. */
export function cursorKey([parliament, from]: OlderCursor): string {
  return `${parliament}:${from}`;
}
