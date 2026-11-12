import { Inter } from 'next/font/google';

// next/font self-hosts the family at build time: no request to Google from
// the visitor's browser. Shared by the route-group layout and by portals (the
// detail dialog renders outside the layout's DOM subtree, so it has to set the
// font variables itself).
const inter = Inter({
  subsets: ['latin'],
  variable: '--font-daily-body',
  display: 'swap',
});

/** Classes that define the feed's font variable and theme tokens. */
export const DAILY_THEME_CLASSES = `daily-theme ${inter.variable}`;
