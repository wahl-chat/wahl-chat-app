import { Bricolage_Grotesque, Tinos } from 'next/font/google';

// next/font self-hosts both families at build time, so a player's browser
// never asks Google for them.

/** The game's own voice: its name, the start button, the score, the countdown. */
const display = Bricolage_Grotesque({
  subsets: ['latin'],
  weight: ['500', '600', '700', '800'],
  variable: '--font-stimmts-display',
  display: 'swap',
});

/**
 * The bill sheet's text. Tinos has the metrics of the Times New Roman a
 * Drucksache is set in, so the sheet reads like the printed paper on every
 * phone, including those without Times.
 */
const document = Tinos({
  subsets: ['latin'],
  weight: ['400', '700'],
  style: ['normal', 'italic'],
  variable: '--font-stimmts-document',
  display: 'swap',
});

/** Defines `font-display` and `font-document` for everything inside. */
export const STIMMTS_FONT_CLASSES = `${display.variable} ${document.variable}`;
