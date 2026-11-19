import { describe, expect, it } from 'bun:test';
import { hasBalancedEmphasis, splitEmphasis, stripEmphasis } from './emphasis';

describe('splitEmphasis', () => {
  it('returns plain text as one segment', () => {
    expect(splitEmphasis('Der Bund zahlt.')).toEqual([
      { text: 'Der Bund zahlt.', strong: false },
    ]);
  });

  it('marks one bold run', () => {
    expect(
      splitEmphasis('Tanken wird bis zu **rund 17 Cent** billiger.'),
    ).toEqual([
      { text: 'Tanken wird bis zu ', strong: false },
      { text: 'rund 17 Cent', strong: true },
      { text: ' billiger.', strong: false },
    ]);
  });

  it('marks several bold runs', () => {
    expect(splitEmphasis('Von **Oktober** bis **Dezember 2026**.')).toEqual([
      { text: 'Von ', strong: false },
      { text: 'Oktober', strong: true },
      { text: ' bis ', strong: false },
      { text: 'Dezember 2026', strong: true },
      { text: '.', strong: false },
    ]);
  });

  it('handles bold at the start and at the end', () => {
    expect(splitEmphasis('**2,5 Milliarden Euro** weniger')).toEqual([
      { text: '2,5 Milliarden Euro', strong: true },
      { text: ' weniger', strong: false },
    ]);
    expect(splitEmphasis('Es kostet **2,5 Milliarden Euro**')).toEqual([
      { text: 'Es kostet ', strong: false },
      { text: '2,5 Milliarden Euro', strong: true },
    ]);
  });

  it('treats unbalanced markers as plain text', () => {
    expect(splitEmphasis('Es kostet **2,5 Milliarden')).toEqual([
      { text: 'Es kostet **2,5 Milliarden', strong: false },
    ]);
    expect(splitEmphasis('**a** und **b')).toEqual([
      { text: '**a** und **b', strong: false },
    ]);
  });

  it('returns no segments for an empty string', () => {
    expect(splitEmphasis('')).toEqual([]);
  });
});

describe('hasBalancedEmphasis', () => {
  it('needs the markers to come in pairs', () => {
    expect(hasBalancedEmphasis('ohne')).toBe(true);
    expect(hasBalancedEmphasis('**a** und **b**')).toBe(true);
    expect(hasBalancedEmphasis('**a')).toBe(false);
  });
});

describe('stripEmphasis', () => {
  it('removes the markers and keeps the text', () => {
    expect(stripEmphasis('bis zu **rund 17 Cent** billiger')).toBe(
      'bis zu rund 17 Cent billiger',
    );
  });
});
