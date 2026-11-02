import createMiddleware from 'next-intl/middleware';
import { NextRequest, NextResponse } from 'next/server';
import { splitLocalePrefix } from './i18n/locale-path';
import { DEFAULT_LOCALE, LOCALE_COOKIE, isLocale } from './i18n/locales';
import { routing } from './i18n/routing';
import {
  CONTEXT_ID_HEADER,
  DEFAULT_CONTEXT_ID,
  REGION_CONTEXTS,
  TENANT_ID_HEADER,
} from './lib/constants';

// Static pages that should remain at root level (not context-specific)
const STATIC_PAGES = [
  '/impressum',
  '/datenschutz',
  '/about-us',
  '/how-to',
  '/budget-spent',
  '/login',
  '/donate',
  '/topics',
  '/aktuell',
  '/api',
];

// File-based metadata routes. The matcher already skips paths with a file
// extension; listed anyway because they must be served whatever else is going
// on — a sitemap or robots.txt answering with a redirect is worse than one
// answering with stale content.
const METADATA_ROUTES = [
  '/sitemap.xml',
  '/robots.txt',
  '/manifest.json',
  '/icon.png',
  '/icon.svg',
  '/apple-icon.png',
];

// Check if the pathname is a static page
function isStaticPage(pathname: string): boolean {
  return (
    METADATA_ROUTES.includes(pathname) ||
    STATIC_PAGES.some(
      (page) => pathname === page || pathname.startsWith(`${page}/`),
    )
  );
}

const handleI18nRouting = createMiddleware(routing);

const ELECTION_PAST_BUFFER_MS = 5 * 24 * 60 * 60 * 1000;

function isElectionPast(electionDate: string): boolean {
  return (
    new Date(electionDate).getTime() < Date.now() - ELECTION_PAST_BUFFER_MS
  );
}

// Election a context-less legacy link should land on. Region-derived rather
// than fixed so these links keep resolving as elections conclude. Only these
// redirects may vary by requester: / must serve identical content to crawlers
// and visitors, so it never consults this.
function getContextIdFromGeo(request: NextRequest): string {
  const country = request.headers.get('x-vercel-ip-country');
  const region = request.headers.get('x-vercel-ip-country-region');
  const context = country === 'DE' && region ? REGION_CONTEXTS[region] : null;

  return context && !isElectionPast(context.electionDate)
    ? context.contextId
    : DEFAULT_CONTEXT_ID;
}

// Known context ID patterns (will be validated against actual contexts)
function looksLikeContextId(segment: string): boolean {
  // Context IDs are like: bundestagswahl-2025, bw2026, europawahl-2029
  return /^[a-z]{2,}\d{4}$|^[a-z]+-[a-z]+-\d{4}$|^[a-z]+wahl-\d{4}$/.test(
    segment,
  );
}

// Helper to build redirect URL with search params preserved
function buildRedirectUrl(
  request: NextRequest,
  path: string,
  preserveParams = true,
): URL {
  const searchParams = preserveParams
    ? request.nextUrl.searchParams.toString()
    : '';
  return new URL(
    `${path}${searchParams ? `?${searchParams}` : ''}`,
    request.url,
  );
}

export async function middleware(request: NextRequest) {
  const { prefix, path: pathname } = splitLocalePrefix(
    request.nextUrl.pathname,
  );

  // A reader who chose a language keeps it on prefix-less links. Crawlers
  // carry no cookie, so / stays the same page for them.
  const chosen = request.cookies.get(LOCALE_COOKIE)?.value;
  if (!prefix && chosen && chosen !== DEFAULT_LOCALE && isLocale(chosen)) {
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `/${chosen}${pathname === '/' ? '' : pathname}`,
      ),
    );
  }

  // Handle tenant ID from search params
  const tenantIdSearchParam = request.nextUrl.searchParams.get('tenant_id');
  const requestHeaders = new Headers(request.headers);

  if (tenantIdSearchParam) {
    requestHeaders.set(TENANT_ID_HEADER, tenantIdSearchParam);
  }

  // Skip middleware for static pages. This has to run before the BUDGET_SPENT
  // check: /budget-spent is itself a static page, so checking the flag first
  // redirected the kill-switch landing page to itself forever, and sent
  // /sitemap.xml, /robots.txt and /manifest.json there too.
  if (isStaticPage(pathname)) {
    return localized(request, requestHeaders);
  }

  if (process.env.BUDGET_SPENT === 'true') {
    return NextResponse.redirect(
      new URL(`${prefix}/budget-spent`, request.url),
    );
  }

  // Legacy context-less URLs. Bare paths go to /, which is stable — so those
  // can be permanent (308) and consolidate their link equity. Paths carrying a
  // party or session still need a context, and middleware can only guess one
  // from the request's region, so those stay temporary (307). Bare /chat is
  // not legacy: it is the chat landing page.

  if (pathname.startsWith('/chat/')) {
    const partyId = pathname.split('/')[2];
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `${prefix}/${getContextIdFromGeo(request)}/session?party_id=${partyId}`,
      ),
    );
  }

  if (pathname === '/session') {
    return NextResponse.redirect(buildRedirectUrl(request, prefix || '/'), 308);
  }

  if (pathname.startsWith('/session/')) {
    const restPath = pathname.replace('/session', '');
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `${prefix}/${getContextIdFromGeo(request)}/session${restPath}`,
      ),
    );
  }

  if (pathname === '/swiper' || pathname.startsWith('/swiper/')) {
    const restPath = pathname.replace('/swiper', '');
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `${prefix}/${getContextIdFromGeo(request)}/swiper${restPath}`,
      ),
    );
  }

  if (pathname === '/share') {
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `${prefix}/${getContextIdFromGeo(request)}/share`,
      ),
    );
  }

  // Not sent to /, which has no source list — a context's sources page is a far
  // better answer to /sources than the landing page.
  if (pathname === '/sources') {
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `${prefix}/${getContextIdFromGeo(request)}/sources`,
      ),
    );
  }

  // Extract context ID from path for context-specific routes
  const segments = pathname.split('/').filter(Boolean);
  const potentialContextId = segments[0];

  if (potentialContextId && looksLikeContextId(potentialContextId)) {
    requestHeaders.set(CONTEXT_ID_HEADER, potentialContextId);
  }

  return localized(request, requestHeaders);
}

/** Hand over to next-intl, which maps the URL onto app/[locale]/…, carrying
 * the tenant and context headers set above into the rewritten request. */
function localized(request: NextRequest, headers: Headers) {
  return handleI18nRouting(new NextRequest(request, { headers }));
}

export const config = {
  // Every page, since each one is served from app/[locale]/…. / is never
  // redirected by IP: varying it would send crawlers and German visitors to
  // different elections and point inbound links at a redirect. API routes,
  // Next internals and files (sitemap.xml, robots.txt, icons) are left alone.
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)'],
};
