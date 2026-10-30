import { describe, expect, it } from 'bun:test';
import { encodePeriod } from './period';
import {
  parseShareParams,
  shareImagePath,
  sharedResultPath,
} from './share-image';

const PUZZLE_COUNT = 40;

const parse = (query: string) =>
  parseShareParams(new URLSearchParams(query), PUZZLE_COUNT);

describe('parseShareParams', () => {
  it('reads a shared result with its period', () => {
    const data = parse('f=square&n=4&s=4&d=2026-11-04&p=5x34');
    expect(data).toMatchObject({
      format: 'square',
      result: { number: 4, playDate: '2026-11-04', score: 4 },
    });
    expect(data?.result?.days?.map((day) => day.kind)).toEqual([
      'played',
      'missed',
      'played',
      'played',
    ]);
    expect(data?.result?.days?.map((day) => day.playDate)).toEqual([
      '2026-11-01',
      '2026-11-02',
      '2026-11-03',
      '2026-11-04',
    ]);
    expect(encodePeriod(data?.result?.days ?? [])).toBe('5x34');
  });

  it('reads the plain game link, which shows no day', () => {
    expect(parse('f=link')).toEqual({ format: 'link' });
  });

  it('counts the period from its own first day after day 30', () => {
    const data = parse('f=story&n=32&s=5&d=2026-12-02&p=45');
    expect(data?.result?.days?.map((day) => day.number)).toEqual([31, 32]);
  });

  it.each([
    ['an unknown format', 'f=poster&n=1&s=3&d=2026-11-01'],
    ['an inherited property as the format', 'f=constructor'],
    ['a square without a result', 'f=square'],
    ['a missing number', 's=3&d=2026-11-01'],
    ['a number past the last puzzle', 'n=41&s=3&d=2026-11-01'],
    ['puzzle zero', 'n=0&s=3&d=2026-11-01'],
    ['a missing score', 'n=1&d=2026-11-01'],
    ['a score above five', 'n=1&s=6&d=2026-11-01'],
    ['a score that is not a number', 'n=1&s=vier&d=2026-11-01'],
    ['a missing day', 'n=1&s=3'],
    ['a day that does not exist', 'n=1&s=3&d=2026-02-31'],
    ['a period of the wrong length', 'n=3&s=4&d=2026-11-03&p=44'],
    ['a period that ends on another score', 'n=2&s=4&d=2026-11-02&p=45'],
    ['a period with other characters', 'n=2&s=4&d=2026-11-02&p=4<'],
  ])('refuses %s', (_, query) => {
    expect(parse(query)).toBeNull();
  });
});

describe('share paths', () => {
  it('round-trips through parseShareParams', () => {
    const path = shareImagePath('story', {
      number: 3,
      score: 2,
      playDate: '2026-11-03',
      period: '4x2',
    });
    const query = path.slice(path.indexOf('?'));
    expect(parse(query)).toMatchObject({
      format: 'story',
      result: { number: 3, score: 2, playDate: '2026-11-03' },
    });
  });

  it('links the plain game card without a day', () => {
    expect(shareImagePath('link')).toBe('/stimmts/share?f=link');
  });

  it('links a result to the game with its number, score and day only', () => {
    expect(
      sharedResultPath({
        number: 10,
        score: 4,
        playDate: '2026-11-10',
        period: '4444444444',
      }),
    ).toBe('/stimmts?n=10&s=4&d=2026-11-10');
  });
});
