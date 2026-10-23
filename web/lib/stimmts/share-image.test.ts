import { describe, expect, it } from 'bun:test';
import { encodePeriod } from './period';
import {
  parseShareParams,
  shareImagePath,
  sharedResultPath,
} from './share-image';
import type { Schedule } from './types';

const SCHEDULE: Schedule = {
  startDate: '2026-11-01',
  puzzleIds: Array.from({ length: 40 }, (_, i) => `puzzle-${i + 1}`),
};

const parse = (query: string) =>
  parseShareParams(new URLSearchParams(query), SCHEDULE);

describe('parseShareParams', () => {
  it('reads a shared result with its period', () => {
    const data = parse('f=square&n=4&s=4&p=5x34');
    expect(data).toMatchObject({
      format: 'square',
      number: 4,
      playDate: '2026-11-04',
      score: 4,
    });
    expect(data?.days?.map((day) => day.kind)).toEqual([
      'played',
      'missed',
      'played',
      'played',
    ]);
    expect(encodePeriod(data?.days ?? [])).toBe('5x34');
  });

  it('reads the plain game link without a score', () => {
    expect(parse('f=link&n=1')).toEqual({
      format: 'link',
      number: 1,
      playDate: '2026-11-01',
    });
  });

  it('counts the period from its own first day after day 30', () => {
    const data = parse('f=story&n=32&s=5&p=45');
    expect(data?.days?.map((day) => day.number)).toEqual([31, 32]);
  });

  it.each([
    ['an unknown format', 'f=poster&n=1'],
    ['a missing number', 'f=square'],
    ['a number outside the schedule', 'n=41'],
    ['puzzle zero', 'n=0'],
    ['a score above five', 'n=1&s=6'],
    ['a score that is not a number', 'n=1&s=vier'],
    ['a period without a score', 'n=2&p=44'],
    ['a period of the wrong length', 'n=3&s=4&p=44'],
    ['a period that ends on another score', 'n=2&s=4&p=45'],
    ['a period with other characters', 'n=2&s=4&p=4<'],
  ])('refuses %s', (_, query) => {
    expect(parse(query)).toBeNull();
  });
});

describe('share paths', () => {
  it('round-trips through parseShareParams', () => {
    const path = shareImagePath({
      format: 'story',
      number: 3,
      score: 2,
      period: '4x2',
    });
    const query = path.slice(path.indexOf('?'));
    expect(parse(query)).toMatchObject({
      format: 'story',
      number: 3,
      score: 2,
    });
  });

  it('links a result to the game with its number and score only', () => {
    expect(sharedResultPath(10, 4)).toBe('/stimmts?n=10&s=4');
  });
});
