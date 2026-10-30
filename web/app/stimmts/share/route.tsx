import ShareImage, {
  SHARE_FONTS,
  SHARE_IMAGE_TEXT,
} from '@/components/stimmts/share-image';
import { loadGoogleFont } from '@/lib/og/google-font';
import { PUZZLE_COUNT } from '@/lib/stimmts/content';
import { createLoadOnce } from '@/lib/stimmts/load-once';
import {
  SHARE_FORMATS,
  canonicalSharePath,
  parseShareParams,
} from '@/lib/stimmts/share-image';
import { ImageResponse } from 'next/og';

// The images are drawn from their parameters alone, so a URL always draws the
// same PNG and the CDN may keep it as long as the deployment lives (a new
// deployment starts a fresh cache). Browsers only keep it a day, so a change
// to the design reaches them. Never cached while developing.
const CACHE_CONTROL =
  process.env.NODE_ENV === 'development'
    ? 'no-store'
    : 'public, max-age=86400, s-maxage=31536000, stale-while-revalidate=86400';

const loadFonts = createLoadOnce(async () => {
  const [display, sans, sansBold] = await Promise.all([
    loadGoogleFont('Bricolage+Grotesque:wght@800', SHARE_IMAGE_TEXT),
    loadGoogleFont('Arimo:wght@400', SHARE_IMAGE_TEXT),
    loadGoogleFont('Arimo:wght@700', SHARE_IMAGE_TEXT),
  ]);
  return [
    { name: SHARE_FONTS.display, data: display, weight: 800 as const },
    { name: SHARE_FONTS.sans, data: sans, weight: 400 as const },
    { name: SHARE_FONTS.sans, data: sansBold, weight: 700 as const },
  ];
});

/**
 * The Stimmt's? share image, for the share sheet and for link previews. Its
 * parameters say everything it shows (number, score, day, the player's
 * period), so nothing is stored on a server.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const data = parseShareParams(url.searchParams, PUZZLE_COUNT);
  if (!data) {
    return new Response('Invalid share image parameters', { status: 400 });
  }
  const canonical = canonicalSharePath(data);
  if (`${url.pathname}${url.search}` !== canonical) {
    return Response.redirect(new URL(canonical, url), 308);
  }

  // Without the fonts the image still draws, in next/og's own face, and is
  // not cached, so the next request tries the fonts again.
  const fonts = await loadFonts();
  const { width, height } = SHARE_FORMATS[data.format];
  return new ImageResponse(<ShareImage {...data} />, {
    width,
    height,
    // Left out, not empty: an empty list leaves next/og no font at all.
    ...(fonts && { fonts }),
    headers: {
      'Cache-Control': fonts ? CACHE_CONTROL : 'no-store',
      'X-Robots-Tag': 'noindex',
    },
  });
}
