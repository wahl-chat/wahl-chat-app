import { BASE_URL, IS_INDEXABLE } from '@/lib/seo';
import type { MetadataRoute } from 'next';

export default function robots(): MetadataRoute.Robots {
  // Previews and the embed deployment must not be crawled at all, and must not
  // advertise the production sitemap. Keep this in step with the meta robots
  // tag (lib/seo.ts) so robots.txt and the pages never disagree.
  if (!IS_INDEXABLE) {
    return {
      rules: {
        userAgent: '*',
        disallow: '/',
      },
    };
  }

  return {
    rules: {
      userAgent: '*',
      allow: '/',
    },
    sitemap: `${BASE_URL}/sitemap.xml`,
  };
}
