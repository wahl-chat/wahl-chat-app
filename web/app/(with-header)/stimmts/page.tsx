import StimmtsGame from '@/components/stimmts/stimmts-game';
import { berlinDate } from '@/lib/stimmts/berlin-time';
import { PUZZLE_COUNT } from '@/lib/stimmts/content';
import { STIMMTS_FONT_CLASSES } from '@/lib/stimmts/fonts';
import { isPreviewEnabled } from '@/lib/stimmts/preview';
import {
  SHARE_FORMATS,
  parseShareParams,
  shareImagePath,
} from '@/lib/stimmts/share-image';
import type { Metadata } from 'next';

const DESCRIPTION =
  'Das tägliche Rätsel von wahl.chat: Wie haben die Parteien im Bundestag abgestimmt?';

type Props = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

/**
 * A shared result links here with its number, score and day (?n=…&s=…&d=…),
 * and its preview shows that card; the plain link shows the game's own card,
 * which names no day, so it is right whether or not the game is running.
 */
export async function generateMetadata({
  searchParams,
}: Props): Promise<Metadata> {
  const params = await searchParams;
  const query = new URLSearchParams({ f: 'link' });
  for (const key of ['n', 's', 'd']) {
    const value = params[key];
    if (typeof value === 'string') {
      query.set(key, value);
    }
  }
  const result = parseShareParams(
    query,
    PUZZLE_COUNT,
    berlinDate(new Date()),
  )?.result;
  const image = {
    url: shareImagePath('link', result),
    ...SHARE_FORMATS.link,
    alt: "Stimmt's?, das tägliche Rätsel von wahl.chat",
  };

  return {
    title: "Stimmt's?",
    description: DESCRIPTION,
    // Stays out of search results until the game is released.
    robots: 'noindex',
    openGraph: {
      title: "Stimmt's?",
      description: DESCRIPTION,
      images: [image],
    },
    twitter: { card: 'summary_large_image', images: [image] },
  };
}

function StimmtsPage() {
  const previewEnabled = isPreviewEnabled({
    vercelEnv: process.env.VERCEL_ENV,
    nodeEnv: process.env.NODE_ENV,
    flag: process.env.NEXT_PUBLIC_STIMMTS_PREVIEW,
  });
  return (
    <div className={STIMMTS_FONT_CLASSES}>
      <StimmtsGame previewEnabled={previewEnabled} />
    </div>
  );
}

export default StimmtsPage;
