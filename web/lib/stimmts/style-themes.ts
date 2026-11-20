import type { StyleId } from './styles';

export type StyleTheme = {
  /** The panel the result screen sits on. */
  canvas: string;
  /** Pills, tracks and the secondary button. */
  surface: string;
  border: string;
  ink: string;
  muted: string;
  /** Which of the site's two palettes the style's colours belong with. */
  mode: 'light' | 'dark';
  /** Headlines in the bill sheet's Tinos instead of the game's display face. */
  displayFont?: 'document';
};

/**
 * Each style is one fixed palette, whatever the site's light or dark mode,
 * because its decoration is drawn for that palette. Only the neutral tokens
 * change: seat and verdict colours carry meaning and stay as they are.
 */
export const STYLE_THEMES: Record<Exclude<StyleId, 'standard'>, StyleTheme> = {
  papier: {
    canvas: '#f3e9d2',
    surface: '#e6d8b8',
    border: '#d3c29c',
    ink: '#2a2116',
    muted: '#65573f',
    mode: 'light',
    displayFont: 'document',
  },
  kuppel: {
    canvas: '#e9f0f6',
    surface: '#d6e1eb',
    border: '#bccbda',
    ink: '#0f1b2a',
    muted: '#475b6e',
    mode: 'light',
  },
  nacht: {
    canvas: '#0b1226',
    surface: '#18213d',
    border: '#27304d',
    ink: '#e8edf7',
    muted: '#9aa6c0',
    mode: 'dark',
  },
  festlich: {
    canvas: '#0f1a14',
    surface: '#1b2a21',
    border: '#2b3d31',
    ink: '#fbf5e6',
    muted: '#b3bdb5',
    mode: 'dark',
  },
  gold: {
    canvas: '#12100b',
    surface: '#221d13',
    border: '#3a3120',
    ink: '#f6efdc',
    muted: '#b0a68e',
    mode: 'dark',
  },
};

/**
 * The feed's tokens a style overrides, as inline custom properties. Body text
 * takes the muted colour: the palettes have no third grey, and muted already
 * meets 4.5:1 on canvas and surface.
 */
export function styleVars(id: StyleId): Record<string, string> {
  if (id === 'standard') {
    return {};
  }
  const theme = STYLE_THEMES[id];
  return {
    '--daily-canvas': theme.canvas,
    '--daily-surface': theme.surface,
    '--daily-border': theme.border,
    '--daily-ink': theme.ink,
    '--daily-muted': theme.muted,
    '--daily-body': theme.muted,
  };
}

/**
 * The right/wrong dots and the glyph on them, per palette lightness. The site
 * switches these with its own light or dark mode, but under a style they sit
 * on the style's canvas, so they have to follow the style instead.
 */
export const VERDICT_COLOURS = {
  light: { correct: '#15803d', wrong: '#b91c1c', glyph: '#ffffff' },
  dark: { correct: '#4ade80', wrong: '#f87171', glyph: '#0b0b0b' },
} as const;

/**
 * The site colours (space-separated channels, as globals.css declares them)
 * that the result screen reads outside the feed's tokens: the urn's outline
 * and the cast hint follow the foreground/background pair.
 */
const SITE_COLOURS = {
  light: {
    '--background': '0 0% 100%',
    '--foreground': '240 10% 3.9%',
    '--muted-foreground': '240 3.8% 46.1%',
  },
  dark: {
    '--background': '240 10% 3.9%',
    '--foreground': '0 0% 98%',
    '--muted-foreground': '240 5% 64.9%',
  },
} as const;

function channels(hex: string): string {
  return [1, 3, 5]
    .map((i) => Number.parseInt(hex.slice(i, i + 2), 16))
    .join(' ');
}

/**
 * Overrides for the colours that otherwise follow the site's light or dark
 * mode, set to the style's own lightness. Seat colours are not among them:
 * they carry meaning and never change.
 */
export function modeVars(id: StyleId): Record<string, string> {
  if (id === 'standard') {
    return {};
  }
  const mode = STYLE_THEMES[id].mode;
  const verdict = VERDICT_COLOURS[mode];
  return {
    ...SITE_COLOURS[mode],
    '--result-correct': channels(verdict.correct),
    '--result-wrong': channels(verdict.wrong),
    '--result-glyph': verdict.glyph,
  };
}
