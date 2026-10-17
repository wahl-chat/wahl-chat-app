import { describe, expect, it } from 'bun:test';
import { matchesTopics, parseTopicsParam } from './topics';

describe('matchesTopics', () => {
  it('treats an empty selection as everything', () => {
    expect(matchesTopics(['other'], [])).toBe(true);
  });

  it('matches when any item topic is selected', () => {
    expect(
      matchesTopics(['housing_rent', 'social_labor'], ['social_labor']),
    ).toBe(true);
    expect(matchesTopics(['housing_rent'], ['health_care'])).toBe(false);
  });
});

describe('parseTopicsParam', () => {
  it('keeps known topics once and drops the rest', () => {
    expect(parseTopicsParam('housing_rent,nope,housing_rent,other')).toEqual([
      'housing_rent',
      'other',
    ]);
    expect(parseTopicsParam(undefined)).toEqual([]);
  });
});
