import { DEFAULT_LOCALE, isLocale } from './locales';

/**
 * `/en/session/x` → `{ prefix: '/en', path: '/session/x' }`. German has no
 * prefix. The middleware's rules work on `path`, and its redirects put `prefix`
 * back, so a reader keeps their language through legacy links.
 */
export function splitLocalePrefix(pathname: string): {
  prefix: string;
  path: string;
} {
  const first = pathname.split('/')[1];
  if (first && first !== DEFAULT_LOCALE && isLocale(first)) {
    return {
      prefix: `/${first}`,
      path: pathname.slice(first.length + 1) || '/',
    };
  }
  return { prefix: '', path: pathname };
}
