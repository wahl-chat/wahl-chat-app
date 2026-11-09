import { describe, expect, it } from 'bun:test';
import type { FeedPage } from '@/lib/firebase/firebase.types';
import { type Pages, appendPages, cursorKey, olderCursors } from './paging';

const page = (from: string | null, hasOlder: boolean): FeedPage => ({
  editions: [],
  items: [],
  from,
  hasOlder,
});

const PAGES: Pages = {
  bundestag: [page('2026-10-23', true)],
  landtag_st: [page('2026-09-01', false)],
  landtag_bw: [page(null, false)],
};

describe('olderCursors', () => {
  it('names the selected parliaments with an older slice', () => {
    expect(olderCursors(PAGES, ['bundestag', 'landtag_st'])).toEqual([
      ['bundestag', '2026-10-23'],
    ]);
  });

  it('follows the last loaded slice', () => {
    const pages = appendPages(PAGES, [
      ['bundestag', page('2026-10-07', false)],
    ]);
    expect(olderCursors(pages, ['bundestag'])).toEqual([]);
  });
});

describe('appendPages', () => {
  it('adds each slice to its own parliament and leaves the input alone', () => {
    const older = page('2026-10-07', true);
    const next = appendPages(PAGES, [['bundestag', older]]);
    expect(next.bundestag).toEqual([PAGES.bundestag[0], older]);
    expect(next.landtag_st).toBe(PAGES.landtag_st);
    expect(PAGES.bundestag).toHaveLength(1);
  });
});

describe('cursorKey', () => {
  it('is one key per parliament and cursor', () => {
    expect(cursorKey(['bundestag', '2026-10-23'])).toBe('bundestag:2026-10-23');
  });
});
