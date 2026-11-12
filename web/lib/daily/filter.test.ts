import { describe, expect, it } from 'bun:test';
import {
  DEFAULT_FILTER,
  FEED_KINDS,
  activeFilterCount,
  isDefaultFilter,
  kindParamValue,
  parseKindParam,
} from './filter';

describe('kind param', () => {
  it('round-trips each single kind through the URL', () => {
    for (const kind of FEED_KINDS) {
      expect(parseKindParam(kindParamValue([kind]))).toEqual([kind]);
    }
  });

  it('leaves the param out when both kinds are shown', () => {
    expect(kindParamValue(FEED_KINDS)).toBeNull();
    expect(parseKindParam(null)).toEqual([...FEED_KINDS]);
  });

  it('shows both kinds for an unknown value rather than nothing', () => {
    expect(parseKindParam('reden')).toEqual([...FEED_KINDS]);
    expect(parseKindParam('')).toEqual([...FEED_KINDS]);
    expect(parseKindParam(['abstimmungen', 'debatten'])).toEqual(['vote']);
  });
});

describe('activeFilterCount', () => {
  it('counts each topic and one for a left-out kind', () => {
    expect(activeFilterCount(DEFAULT_FILTER)).toBe(0);
    expect(isDefaultFilter(DEFAULT_FILTER)).toBe(true);
    expect(
      activeFilterCount({ topics: ['health_care', 'other'], kinds: ['vote'] }),
    ).toBe(3);
    expect(isDefaultFilter({ ...DEFAULT_FILTER, kinds: ['debate'] })).toBe(
      false,
    );
  });
});
