import { DM_Sans, Playfair_Display } from 'next/font/google';

// next/font self-hosts both families at build time: no request to Google
// from the visitor's browser. Shared by the route-group layout and by portals
// (the detail dialog renders outside the layout's DOM subtree, so it has to
// set the font variables itself).
const display = Playfair_Display({
  subsets: ['latin'],
  weight: ['700', '800', '900'],
  style: ['normal', 'italic'],
  variable: '--font-daily-display',
  display: 'swap',
});

const body = DM_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '700'],
  variable: '--font-daily-body',
  display: 'swap',
});

/** Classes that define the feed's font variables and theme tokens. */
export const DAILY_THEME_CLASSES = `daily-theme ${display.variable} ${body.variable}`;
