import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import {
  CONTEXT_ID_HEADER,
  DEFAULT_CONTEXT_ID,
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
  '/api',
];

// File-based metadata routes. The '/:contextId' matcher catches these, and they
// must be served whatever else is going on — a sitemap or robots.txt answering
// with a redirect is worse than one answering with stale content.
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
  const pathname = request.nextUrl.pathname;

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
    return NextResponse.next({
      request: { headers: requestHeaders },
    });
  }

  if (process.env.BUDGET_SPENT === 'true') {
    return NextResponse.redirect(new URL('/budget-spent', request.url));
  }

  // Legacy context-less URLs. Bare paths go to /, which is stable and lets the
  // visitor pick their own election — so those can be permanent (308) and
  // consolidate their link equity. Paths carrying a party or session still need
  // a context, and DEFAULT_CONTEXT_ID is the only one middleware can reach
  // without Firestore, so those stay temporary (307).
  if (pathname === '/chat') {
    return NextResponse.redirect(buildRedirectUrl(request, '/'), 308);
  }

  if (pathname.startsWith('/chat/')) {
    const partyId = pathname.split('/')[2];
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `/${DEFAULT_CONTEXT_ID}/session?party_id=${partyId}`,
      ),
    );
  }

  if (pathname === '/session') {
    return NextResponse.redirect(buildRedirectUrl(request, '/'), 308);
  }

  if (pathname.startsWith('/session/')) {
    const restPath = pathname.replace('/session', '');
    return NextResponse.redirect(
      buildRedirectUrl(request, `/${DEFAULT_CONTEXT_ID}/session${restPath}`),
    );
  }

  if (pathname === '/swiper' || pathname.startsWith('/swiper/')) {
    const restPath = pathname.replace('/swiper', '');
    return NextResponse.redirect(
      buildRedirectUrl(request, `/${DEFAULT_CONTEXT_ID}/swiper${restPath}`),
    );
  }

  if (pathname === '/share') {
    return NextResponse.redirect(
      buildRedirectUrl(request, `/${DEFAULT_CONTEXT_ID}/share`),
    );
  }

  // Not sent to /, which has no source list — a context's sources page is a far
  // better answer to /sources than the landing page.
  if (pathname === '/sources') {
    return NextResponse.redirect(
      buildRedirectUrl(request, `/${DEFAULT_CONTEXT_ID}/sources`),
    );
  }

  // Extract context ID from path for context-specific routes
  const segments = pathname.split('/').filter(Boolean);
  const potentialContextId = segments[0];

  if (potentialContextId && looksLikeContextId(potentialContextId)) {
    requestHeaders.set(CONTEXT_ID_HEADER, potentialContextId);
  }

  return NextResponse.next({
    request: { headers: requestHeaders },
  });
}

export const config = {
  matcher: [
    // '/' is matched for the tenant header and the BUDGET_SPENT kill switch, not
    // for routing: it serves the landing page directly now. Routing it by IP made
    // crawlers and German visitors land on different elections, and pointed every
    // inbound link at a redirect instead of a page.
    '/',
    '/chat/:path*',
    '/session/:path*',
    '/swiper/:path*',
    '/share',
    '/sources',
    '/:contextId',
    '/:contextId/:path*',
  ],
};
