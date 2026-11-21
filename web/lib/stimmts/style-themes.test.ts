import { describe, expect, it } from 'bun:test';
import {
  FESTLICH_GROUND,
  FESTLICH_TREE,
  GOLD_CORNER,
  STYLE_THEMES,
  VERDICT_COLOURS,
  modeVars,
  styleVars,
} from './style-themes';
import type { StyleId } from './styles';

const THEMED: Exclude<StyleId, 'standard'>[] = [
  'papier',
  'kuppel',
  'nacht',
  'festlich',
  'gold',
];

const DAILY_VARS = [
  '--daily-canvas',
  '--daily-surface',
  '--daily-border',
  '--daily-ink',
  '--daily-muted',
  '--daily-body',
];

describe('styleVars', () => {
  it('standard adds no variables', () => {
    expect(styleVars('standard')).toEqual({});
  });

  it('every theme sets the six --daily vars', () => {
    for (const id of THEMED) {
      const vars = styleVars(id);
      expect(Object.keys(vars).sort()).toEqual([...DAILY_VARS].sort());
      expect(vars['--daily-body']).toBe(STYLE_THEMES[id].muted);
    }
  });

  it('no theme sets a seat or vote colour variable', () => {
    for (const id of THEMED) {
      for (const name of Object.keys(styleVars(id))) {
        expect(name).not.toMatch(/seat|yes|-no\b|-no-|abstain|result|vote/);
      }
    }
  });

  it('nacht canvas is #0b1226', () => {
    expect(STYLE_THEMES.nacht.canvas).toBe('#0b1226');
    expect(styleVars('nacht')['--daily-canvas']).toBe('#0b1226');
  });
});

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = Number.parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('verdict colours', () => {
  it('every theme picks the verdict pair of its own lightness', () => {
    for (const id of THEMED) {
      const verdict = VERDICT_COLOURS[STYLE_THEMES[id].mode];
      expect(modeVars(id)['--result-glyph']).toBe(verdict.glyph);
    }
    expect(STYLE_THEMES.papier.mode).toBe('light');
    expect(STYLE_THEMES.nacht.mode).toBe('dark');
    expect(VERDICT_COLOURS.light.correct).toBe('#15803d');
  });

  it('the dots reach 3:1 against canvas and surface', () => {
    for (const id of THEMED) {
      const theme = STYLE_THEMES[id];
      const verdict = VERDICT_COLOURS[theme.mode];
      for (const dot of [verdict.correct, verdict.wrong]) {
        expect(contrast(dot, theme.canvas)).toBeGreaterThanOrEqual(3);
        expect(contrast(dot, theme.surface)).toBeGreaterThanOrEqual(3);
      }
    }
  });

  it('the glyph is text, so it reaches 4.5:1 on its dot', () => {
    for (const mode of ['light', 'dark'] as const) {
      const verdict = VERDICT_COLOURS[mode];
      expect(contrast(verdict.glyph, verdict.correct)).toBeGreaterThanOrEqual(
        4.5,
      );
      expect(contrast(verdict.glyph, verdict.wrong)).toBeGreaterThanOrEqual(
        4.5,
      );
    }
  });

  it('standard leaves the site colours alone', () => {
    expect(modeVars('standard')).toEqual({});
  });
});

describe('bottom room', () => {
  it('festlich leaves room for the ground and the whole tree', () => {
    const ground = FESTLICH_GROUND.height - FESTLICH_GROUND.sink;
    const tree = FESTLICH_TREE.lift + FESTLICH_TREE.height;
    expect(STYLE_THEMES.festlich.bottomRoom).toBeGreaterThanOrEqual(
      Math.max(ground, tree),
    );
  });

  it('gold leaves room for its bottom corners', () => {
    expect(STYLE_THEMES.gold.bottomRoom).toBeGreaterThanOrEqual(
      GOLD_CORNER.inset + GOLD_CORNER.size,
    );
  });

  it('no style has less room than the plain panel', () => {
    for (const id of THEMED) {
      expect(STYLE_THEMES[id].bottomRoom).toBeGreaterThanOrEqual(24);
    }
  });
});
