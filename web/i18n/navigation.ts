import { createNavigation } from 'next-intl/navigation';
import { routing } from './routing';

/** Drop-in replacements for `next/link` and `next/navigation` that keep the
 * reader's language in every internal link and redirect. */
export const {
  Link,
  redirect,
  permanentRedirect,
  usePathname,
  useRouter,
  getPathname,
} = createNavigation(routing);
