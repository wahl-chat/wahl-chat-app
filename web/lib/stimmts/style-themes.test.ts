import { describe, expect, it } from 'bun:test';
import { STYLE_THEMES, styleVars } from './style-themes';
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
