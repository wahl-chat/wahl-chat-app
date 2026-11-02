import { getLocale } from 'next-intl/server';
import { permanentRedirect, redirect } from './navigation';

/** `redirect` for server components: keeps the reader's language. */
export async function redirectLocalized(href: string): Promise<never> {
  return redirect({ href, locale: await getLocale() });
}

export async function permanentRedirectLocalized(href: string): Promise<never> {
  return permanentRedirect({ href, locale: await getLocale() });
}
