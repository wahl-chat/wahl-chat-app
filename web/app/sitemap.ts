import { getContexts } from '@/lib/firebase/firebase-server';
import type { MetadataRoute } from 'next';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = 'https://wahl.chat';
  const now = new Date().toISOString();

  const contexts = (await getContexts()) ?? [];
  if (contexts.length === 0) {
    // Intentional fallback: if no contexts are available, the sitemap only includes static pages.
    console.warn('sitemap(): getContexts() returned no contexts; generating sitemap with base URL only.');
  }

  const staticPages: MetadataRoute.Sitemap = [
    { url: baseUrl, lastModified: now, changeFrequency: 'daily', priority: 1 },
  ];

  const contextPages: MetadataRoute.Sitemap = [];

  for (const context of contexts) {
    const id = context.context_id;

    contextPages.push({
      url: `${baseUrl}/${id}`,
      lastModified: now,
      changeFrequency: 'daily',
      priority: 0.9,
    });

    if (context.supports_swiper) {
      contextPages.push({
        url: `${baseUrl}/${id}/swiper`,
        lastModified: now,
        changeFrequency: 'weekly',
        priority: 0.7,
      });
    }
  }

  return [...staticPages, ...contextPages];
}
