import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import {
  CONTEXT_ID_HEADER,
  DEFAULT_CONTEXT_ID,
  REGION_TO_CONTEXT,
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
  '/pdf',
];

// Check if the pathname is a static page
function isStaticPage(pathname: string): boolean {
  return STATIC_PAGES.some(
    (page) => pathname === page || pathname.startsWith(`${page}/`),
  );
}

// Get context ID from Vercel geo headers or fallback to default
function getContextIdFromGeo(request: NextRequest): string {
  // Only consider German regions for now
  const country = request.headers.get('x-vercel-ip-country');
  if (country !== 'DE') {
    return DEFAULT_CONTEXT_ID;
  }

  const region = request.headers.get('x-vercel-ip-country-region');
  if (region && REGION_TO_CONTEXT[region]) {
    return REGION_TO_CONTEXT[region];
  }

  return DEFAULT_CONTEXT_ID;
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
  const budgetSpent = process.env.BUDGET_SPENT === 'true';

  if (budgetSpent) {
    return NextResponse.redirect(new URL('/budget-spent', request.url));
  }

  const pathname = request.nextUrl.pathname;

  // Handle tenant ID from search params
  const tenantIdSearchParam = request.nextUrl.searchParams.get('tenant_id');
  const requestHeaders = new Headers(request.headers);

  if (tenantIdSearchParam) {
    requestHeaders.set(TENANT_ID_HEADER, tenantIdSearchParam);
  }

  // Skip middleware for static pages
  if (isStaticPage(pathname)) {
    return NextResponse.next({
      request: { headers: requestHeaders },
    });
  }

  // Handle legacy /chat routes → redirect to /session with party_id
  if (pathname.startsWith('/chat')) {
    const contextId = DEFAULT_CONTEXT_ID;
    if (pathname === '/chat') {
      return NextResponse.redirect(buildRedirectUrl(request, `/${contextId}`));
    }
    const partyId = pathname.split('/')[2];
    return NextResponse.redirect(
      buildRedirectUrl(request, `/${contextId}/session?party_id=${partyId}`),
    );
  }

  // Root path: detect context from geo and redirect
  if (pathname === '/') {
    const contextId = getContextIdFromGeo(request);
    return NextResponse.redirect(buildRedirectUrl(request, `/${contextId}`));
  }

  // Legacy /session routes → redirect to /{contextId}/session
  if (pathname === '/session' || pathname.startsWith('/session/')) {
    const contextId = DEFAULT_CONTEXT_ID;
    const restPath = pathname.replace('/session', '');
    return NextResponse.redirect(
      buildRedirectUrl(request, `/${contextId}/session${restPath}`),
    );
  }

  // Legacy /swiper routes → redirect to /{contextId}/swiper
  if (pathname === '/swiper' || pathname.startsWith('/swiper/')) {
    const contextId = DEFAULT_CONTEXT_ID;
    const restPath = pathname.replace('/swiper', '');
    return NextResponse.redirect(
      buildRedirectUrl(request, `/${contextId}/swiper${restPath}`),
    );
  }

  // Legacy /share → redirect to /{contextId}/share
  if (pathname === '/share') {
    const contextId = DEFAULT_CONTEXT_ID;
    return NextResponse.redirect(
      buildRedirectUrl(request, `/${contextId}/share`),
    );
  }

  // Legacy /sources → redirect to /{contextId}/sources
  if (pathname === '/sources') {
    const contextId = DEFAULT_CONTEXT_ID;
    return NextResponse.redirect(
      buildRedirectUrl(request, `/${contextId}/sources`),
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
