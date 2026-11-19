import { describe, expect, it } from 'bun:test';
import { itemShareUrl } from './share';

const params = (href: string) => new URL(href).searchParams;

describe('itemShareUrl', () => {
  it('keeps the selected parliaments and topics', () => {
    const url = params(
      itemShareUrl(
        'https://wahl.chat/?land=de,st&themen=health_care',
        'landtag_st_2026-07-10~v7',
        'DE-ST',
      ),
    );
    expect(url.get('land')).toBe('de,st');
    expect(url.get('themen')).toBe('health_care');
    expect(url.get('item')).toBe('landtag_st_2026-07-10~v7');
  });

  it("adds the item's parliament when the URL carries no selection", () => {
    const url = params(
      itemShareUrl('https://wahl.chat/', 'landtag_st_2026-07-10~v7', 'DE-ST'),
    );
    expect(url.get('land')).toBe('st');
  });

  it("adds the item's parliament to a selection without it", () => {
    const url = params(
      itemShareUrl(
        'https://wahl.chat/?land=st',
        'bundestag_2026-07-10~s1',
        'DE',
      ),
    );
    expect(url.get('land')).toBe('st,de');
  });

  it('replaces an item that is already open', () => {
    const url = params(
      itemShareUrl(
        'https://wahl.chat/?land=de&item=old',
        'bundestag_2026-07-10~s1',
        'DE',
      ),
    );
    expect(url.getAll('item')).toEqual(['bundestag_2026-07-10~s1']);
  });
});
