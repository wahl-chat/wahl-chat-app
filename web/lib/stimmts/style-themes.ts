import type { StyleId } from './styles';

export type StyleTheme = {
  /** The panel the result screen sits on. */
  canvas: string;
  /** Pills, tracks and the secondary button. */
  surface: string;
  border: string;
  ink: string;
  muted: string;
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
    displayFont: 'document',
  },
  kuppel: {
    canvas: '#e9f0f6',
    surface: '#d6e1eb',
    border: '#bccbda',
    ink: '#0f1b2a',
    muted: '#475b6e',
  },
  nacht: {
    canvas: '#0b1226',
    surface: '#18213d',
    border: '#27304d',
    ink: '#e8edf7',
    muted: '#9aa6c0',
  },
  festlich: {
    canvas: '#0f1a14',
    surface: '#1b2a21',
    border: '#2b3d31',
    ink: '#fbf5e6',
    muted: '#b3bdb5',
  },
  gold: {
    canvas: '#12100b',
    surface: '#221d13',
    border: '#3a3120',
    ink: '#f6efdc',
    muted: '#b0a68e',
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
