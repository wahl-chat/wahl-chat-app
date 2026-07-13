import { PROXYABLE_PDF_HOSTS } from '@/lib/utils';
import { type NextRequest, NextResponse } from 'next/server';

// Trusted public-institution hosts whose PDFs we stream same-origin so the
// citation viewer can frame them (Bundestag + abgeordnetenwatch block direct
// framing via X-Frame-Options / frame-ancestors). Imported from lib/utils so the
// client-side "is proxyable" check and this allow decision share ONE list. Both
// the initial URL and the post-redirect final URL are validated against it, so
// there is no open-redirect / SSRF surface.
const ALLOWED_HOSTS = PROXYABLE_PDF_HOSTS;

function isAllowed(url: URL): boolean {
  return url.protocol === 'https:' && ALLOWED_HOSTS.has(url.hostname);
}

// Upstreams occasionally serve PDFs as octet-stream; accept both but reject
// anything else (e.g. an HTML error page) so we never frame non-PDF content.
const PDF_CONTENT_TYPES = ['application/pdf', 'application/octet-stream'];

const FETCH_TIMEOUT_MS = 15_000;

/**
 * A framed-error response for runtime failures the <iframe> actually renders.
 *
 * An `<iframe onError>` does NOT fire for an HTTP error that carries a body, so a
 * plain `502 "Upstream returned an error"` paints that raw English text inside the
 * viewer. Instead we return a 200 with a small German HTML page (+ a new-tab escape
 * to the real document) so the user sees a friendly, localized fallback. Framing is
 * still locked to same-origin. `href` is the original allowlisted PDF URL.
 */
function framedError(href: string): NextResponse {
  const safeHref = href.replaceAll('"', '%22');
  const html = `<!doctype html>
<html lang="de">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Beleg nicht verfügbar</title>
<style>
  html,body{height:100%;margin:0}
  body{display:flex;align-items:center;justify-content:center;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#f4f4f5;color:#18181b;padding:1.5rem;text-align:center}
  @media (prefers-color-scheme: dark){body{background:#18181b;color:#e4e4e7}}
  a{display:inline-block;margin-top:1rem;padding:.5rem .9rem;border-radius:.5rem;background:#2563eb;color:#fff;text-decoration:none;font-size:.875rem}
</style>
</head>
<body><div><p>Dieser Beleg konnte hier nicht geladen werden.</p>
<a href="${safeHref}" target="_blank" rel="noopener noreferrer">In neuem Tab öffnen</a></div></body>
</html>`;
  return new NextResponse(html, {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'X-Frame-Options': 'SAMEORIGIN',
      'Content-Security-Policy': "frame-ancestors 'self'",
      'Cache-Control': 'no-store',
    },
  });
}

/**
 * GET /api/pdf-proxy?url=<pdf>
 *
 * Streams an allowlisted PDF back same-origin so the in-page citation viewer can
 * embed it in an <iframe>. Only hosts in ALLOWED_HOSTS are fetched; the response
 * is validated to be a PDF and re-served with same-origin framing headers (the
 * upstream's X-Frame-Options is dropped by not forwarding it).
 */
export async function GET(request: NextRequest) {
  const rawUrl = request.nextUrl.searchParams.get('url');
  if (!rawUrl) {
    return new NextResponse('Missing url parameter', { status: 400 });
  }

  let target: URL;
  try {
    target = new URL(rawUrl);
  } catch {
    return new NextResponse('Invalid url', { status: 400 });
  }

  if (target.protocol !== 'https:') {
    return new NextResponse('Only https URLs are allowed', { status: 400 });
  }
  if (!isAllowed(target)) {
    // Not an SSRF-safe host — the client falls back to opening a new tab.
    return new NextResponse('Host not allowed', { status: 403 });
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  let upstream: Response;
  try {
    upstream = await fetch(target.toString(), {
      // Public documents — never forward cookies/credentials.
      credentials: 'omit',
      redirect: 'follow',
      signal: controller.signal,
      headers: { Accept: 'application/pdf' },
    });
  } catch {
    clearTimeout(timeout);
    return framedError(target.toString());
  }
  clearTimeout(timeout);

  // Re-validate the FINAL url after any redirects: an allowlisted host that
  // 3xx-redirects elsewhere (open redirect / compromise) must not let us stream
  // from an off-allowlist or non-https target. Fail closed → client new-tab.
  try {
    if (!isAllowed(new URL(upstream.url))) {
      // Fail closed on an off-allowlist redirect; the framed page offers new-tab.
      return framedError(target.toString());
    }
  } catch {
    return framedError(target.toString());
  }

  if (!upstream.ok || !upstream.body) {
    return framedError(target.toString());
  }

  const contentType = (
    upstream.headers.get('content-type') ?? ''
  ).toLowerCase();
  const isPdf = PDF_CONTENT_TYPES.some((t) => contentType.startsWith(t));
  if (!isPdf) {
    // Guard against framing an HTML error page or unexpected payload.
    return framedError(target.toString());
  }

  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': 'inline',
      // Same-origin framing only (our own page), and short-lived caching.
      'X-Frame-Options': 'SAMEORIGIN',
      'Content-Security-Policy': "frame-ancestors 'self'",
      'Cache-Control': 'public, max-age=3600',
    },
  });
}
