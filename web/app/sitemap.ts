import { isUpcomingElection } from '@/lib/elections';
import { getContexts } from '@/lib/firebase/firebase-server';
import { BASE_URL } from '@/lib/seo';
import type { MetadataRoute } from 'next';

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
  const staticPages: MetadataRoute.Sitemap = [
    { url: BASE_URL, lastModified: now, changeFrequency: 'daily', priority: 1 },
    {
      url: `${BASE_URL}/how-to`,
      lastModified: now,
      changeFrequency: 'monthly',
      priority: 0.6,
    },
    {
      url: `${BASE_URL}/about-us`,
      lastModified: now,
      changeFrequency: 'monthly',
      priority: 0.5,
    },
  ];

  const contextPages: MetadataRoute.Sitemap = [];

  for (const context of contexts) {
    const id = context.context_id;

    // A concluded election is an archive: still worth indexing, but claiming it
    // changes daily at near-top priority just burns crawl budget.
    const isUpcoming = isUpcomingElection(context);
    const changeFrequency = isUpcoming ? 'daily' : 'yearly';
    const priority = isUpcoming ? 0.9 : 0.4;

    contextPages.push({
      url: `${BASE_URL}/${id}`,
      lastModified: now,
      changeFrequency,
      priority,
    });

    contextPages.push({
      url: `${BASE_URL}/${id}/sources`,
      lastModified: now,
      changeFrequency: isUpcoming ? 'weekly' : 'yearly',
      priority: isUpcoming ? 0.7 : 0.3,
    });
  }

  return [...staticPages, ...contextPages];
}
