import { DEFAULT_LOCALE, type Locale } from '@/i18n/locales';
import { LOGO_IMAGE_URL } from '@/lib/seo';
import type { Metadata } from 'next';
import { type DetailItem, itemTeaser, itemTitle } from './items';

// Previews show two or three lines; past this the text is cut at a word.
const MAX_DESCRIPTION = 300;

export const OG_IMAGE_SIZE = { width: 1200, height: 630 };

/** The chamber image, labelled in the language the link was shared in. */
export function voteImagePath(itemKey: string, locale: Locale): string {
  const path = `/api/og/feed/${encodeURIComponent(itemKey)}`;
  return locale === DEFAULT_LOCALE ? path : `${path}?locale=${locale}`;
}

function truncate(text: string, max: number): string {
  if (text.length <= max) {
    return text;
  }
  const cut = text.slice(0, max - 1);
  const lastSpace = cut.lastIndexOf(' ');
  return `${(lastSpace > 0 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

/** A vote shows its chamber, a debate the frame its card video opens on. */
function previewImage(item: DetailItem, origin: string, locale: Locale) {
  if (item.kind === 'vote') {
    return {
      url: `${origin}${voteImagePath(item.key, locale)}`,
      ...OG_IMAGE_SIZE,
      alt: itemTitle(item),
    };
  }
  return { url: item.section.card_video?.poster_url ?? LOGO_IMAGE_URL };
}

/**
 * What a messenger shows for a link to one feed item: its title, the text
 * the detail view opens with, and its picture.
 *
 * There is no `og:url`: Facebook and WhatsApp re-read the page at that
 * address, and Next writes a URL on `/` as the bare origin, dropping the
 * `?item=` that makes this preview. Without it they keep the link they read.
 */
export function itemShareMetadata(
  item: DetailItem,
  origin: string,
  fallbackDescription: string,
  locale: Locale = DEFAULT_LOCALE,
): Metadata {
  const title = itemTitle(item);
  const teaser = itemTeaser(item);
  const description = teaser
    ? truncate(teaser, MAX_DESCRIPTION)
    : fallbackDescription;
  const image = previewImage(item, origin, locale);
  return {
    openGraph: {
      // Absolute, or the root layout's template appends the brand.
      title: { absolute: title },
      description,
      images: [image],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [image.url],
    },
  };
}
