import StimmtsGame from '@/components/stimmts/stimmts-game';
import { berlinDate, daysBetween } from '@/lib/stimmts/berlin-time';
import { SCHEDULE } from '@/lib/stimmts/content';
import { STIMMTS_FONT_CLASSES } from '@/lib/stimmts/fonts';
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
 * A shared result links here with its number and score (?n=…&s=…), and its
 * preview shows that score; the plain link shows the game's own card.
 */
export async function generateMetadata({
  searchParams,
}: Props): Promise<Metadata> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(await searchParams)) {
    if (typeof value === 'string' && (key === 'n' || key === 's')) {
      query.set(key, value);
    }
  }
  query.set('f', 'link');
  const shared = query.has('n') ? parseShareParams(query, SCHEDULE) : null;
  // The plain link previews today's card (the first one before the start).
  const today = daysBetween(SCHEDULE.startDate, berlinDate(new Date())) + 1;
  const number =
    shared?.number ?? Math.min(Math.max(today, 1), SCHEDULE.puzzleIds.length);
  const image = {
    url: shareImagePath({ format: 'link', number, score: shared?.score }),
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
  return (
    <div className={STIMMTS_FONT_CLASSES}>
      <StimmtsGame />
    </div>
  );
}

export default StimmtsPage;
