import { notFound } from 'next/navigation';

/** Paths no route matches would otherwise get Next's unstyled 404, which
 * sits outside `[locale]` and so has neither the site's layout nor its
 * language. */
export default function CatchAll() {
  notFound();
}
