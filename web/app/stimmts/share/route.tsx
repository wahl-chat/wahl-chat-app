import ShareImage, {
  SHARE_FONTS,
  shareImageText,
} from '@/components/stimmts/share-image';
import { loadGoogleFont } from '@/lib/og/google-font';
import { SCHEDULE } from '@/lib/stimmts/content';
import { SHARE_FORMATS, parseShareParams } from '@/lib/stimmts/share-image';
import { ImageResponse } from 'next/og';

/**
 * The Stimmt's? share image, for the share sheet and for link previews. Its
 * parameters say everything it shows (number, score, the player's period), so
 * nothing is stored on a server, and the same URL always draws the same PNG.
 */
export async function GET(request: Request) {
  const data = parseShareParams(new URL(request.url).searchParams, SCHEDULE);
  if (!data) {
    return new Response('Invalid share image parameters', { status: 400 });
  }

  try {
    const text = shareImageText(data);
    const [display, sans, sansBold] = await Promise.all([
      loadGoogleFont('Bricolage+Grotesque:wght@800', text),
      loadGoogleFont('Arimo:wght@400', text),
      loadGoogleFont('Arimo:wght@700', text),
    ]);
    const { width, height } = SHARE_FORMATS[data.format];
    return new ImageResponse(<ShareImage {...data} />, {
      width,
      height,
      fonts: [
        { name: SHARE_FONTS.display, data: display, weight: 800 },
        { name: SHARE_FONTS.sans, data: sans, weight: 400 },
        { name: SHARE_FONTS.sans, data: sansBold, weight: 700 },
      ],
      headers: {
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    });
  } catch (error) {
    console.error('Stimmts share image failed', error);
    return new Response('Failed to generate the image', { status: 500 });
  }
}
