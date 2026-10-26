import { LOCALES } from '@/i18n/locales';
import { isUpcomingElection } from '@/lib/elections';
import { getContexts } from '@/lib/firebase/firebase-server';
import { localizedUrl } from '@/lib/seo';
import type { MetadataRoute } from 'next';

type SitemapEntry = MetadataRoute.Sitemap[number];
type PageEntry = Omit<SitemapEntry, 'url' | 'alternates'> & { path: string };

/**
 * One entry per language version, each listing every version (itself
 * included) as an alternate — the shape search engines expect for hreflang in
 * a sitemap.
 */
function withLanguageVersions({
  path,
  ...rest
}: PageEntry): MetadataRoute.Sitemap {
  const languages = Object.fromEntries(
    LOCALES.map((locale) => [locale, localizedUrl(path, locale)]),
  );
  return LOCALES.map((locale) => ({
    ...rest,
    url: localizedUrl(path, locale),
    alternates: { languages },
  }));
}

// Without this the route is prerendered at build time (confirmed: the build
// marks /sitemap.xml as Static), so a newly seeded election would not appear
// until the next deploy. getContexts() reads no dynamic API of its own, so
// nothing else opts this route out.
export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date().toISOString();

  const contexts = (await getContexts()) ?? [];
  if (contexts.length === 0) {
    // Intentional fallback: if no contexts are available, the sitemap only includes static pages.
    console.warn(
      'sitemap(): getContexts() returned no contexts; generating sitemap with static pages only.',
    );
  }

  // Only indexable pages belong here. /topics is deliberately excluded: it is
  // context-less and not tied to a current election. The swiper, session, share
  // and agent routes are noindex by design and must never be listed.
  const staticPages: PageEntry[] = [
    { path: '/', lastModified: now, changeFrequency: 'daily', priority: 1 },
    {
      path: '/chat',
      lastModified: now,
      changeFrequency: 'daily',
      priority: 0.9,
    },
    {
      path: '/how-to',
      lastModified: now,
      changeFrequency: 'monthly',
      priority: 0.6,
    },
    {
      path: '/about-us',
      lastModified: now,
      changeFrequency: 'monthly',
      priority: 0.5,
    },
  ];

  const contextPages: PageEntry[] = [];

  for (const context of contexts) {
    const id = context.context_id;

    // A concluded election is an archive: still worth indexing, but claiming it
    // changes daily at near-top priority just burns crawl budget.
    const isUpcoming = isUpcomingElection(context);
    const changeFrequency = isUpcoming ? 'daily' : 'yearly';
    const priority = isUpcoming ? 0.9 : 0.4;

    contextPages.push({
      path: `/${id}`,
      lastModified: now,
      changeFrequency,
      priority,
    });

    contextPages.push({
      path: `/${id}/sources`,
      lastModified: now,
      changeFrequency: isUpcoming ? 'weekly' : 'yearly',
      priority: isUpcoming ? 0.7 : 0.3,
    });
  }

  return [...staticPages, ...contextPages].flatMap(withLanguageVersions);
}
