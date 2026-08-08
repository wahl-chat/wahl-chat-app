import { PROXYABLE_PDF_HOSTS } from '@/lib/utils';
import { type NextRequest, NextResponse } from 'next/server';

// Trusted public-institution hosts whose PDFs we stream same-origin so the
// citation viewer can frame them (Bundestag + abgeordnetenwatch block direct
// framing via X-Frame-Options / frame-ancestors). Imported from lib/utils so the
// client-side "is proxyable" check and this allow decision share ONE list. The
// initial URL and EVERY redirect hop are validated against it before being
// fetched, so there is no open-redirect / SSRF surface.
const ALLOWED_HOSTS = PROXYABLE_PDF_HOSTS;

function isAllowed(url: URL): boolean {
  return url.protocol === 'https:' && ALLOWED_HOSTS.has(url.hostname);
}

// FIX F9: match the chat route's budget so Vercel does not kill long PDF
// streams at the default function timeout.
export const maxDuration = 300;

// Upstreams occasionally serve PDFs as octet-stream; accept both but reject
// anything else (e.g. an HTML error page) so we never frame non-PDF content.
const PDF_CONTENT_TYPES = ['application/pdf', 'application/octet-stream'];

// Budget for receiving response HEADERS (across all redirect hops).
const FETCH_TIMEOUT_MS = 15_000;
// Overall deadline for streaming the response BODY — large plenary PDFs must
// not be able to stall the function forever after headers arrived.
const BODY_DEADLINE_MS = 120_000;
// Redirect hops we are willing to follow (each hop is re-validated).
const MAX_REDIRECTS = 5;

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
      'X-Content-Type-Options': 'nosniff',
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
  const headerTimeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  // FIX F6: follow redirects MANUALLY, validating EVERY hop's Location against
  // the https + host allowlist BEFORE fetching it. `redirect: 'follow'` only
  // let us validate the final URL — an open redirect on an allowlisted host
  // could still fire unvalidated intermediate requests (blind GET SSRF).
  let upstream: Response;
  try {
    let current = target;
    let hops = 0;
    for (;;) {
      const response = await fetch(current.toString(), {
        // Public documents — never forward cookies/credentials.
        credentials: 'omit',
        redirect: 'manual',
        signal: controller.signal,
        headers: { Accept: 'application/pdf' },
      });

      if (response.status >= 300 && response.status < 400) {
        hops += 1;
        if (hops > MAX_REDIRECTS) {
          return framedError(target.toString());
        }
        const location = response.headers.get('location');
        if (!location) {
          return framedError(target.toString());
        }
        let next: URL;
        try {
          next = new URL(location, current);
        } catch {
          return framedError(target.toString());
        }
        // Fail closed: every hop must be https AND on the host allowlist.
        if (!isAllowed(next)) {
          return framedError(target.toString());
        }
        current = next;
        continue;
      }

      upstream = response;
      break;
    }
  } catch {
    return framedError(target.toString());
  } finally {
    clearTimeout(headerTimeout);
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

  // FIX F9: overall deadline covering BODY streaming — the previous
  // clearTimeout-after-headers left large PDFs free to stall mid-stream
  // indefinitely. The timer aborts the upstream fetch; it is cleared when the
  // body finishes streaming (abort after completion is a harmless no-op).
  const bodyDeadline = setTimeout(() => controller.abort(), BODY_DEADLINE_MS);
  const body = upstream.body.pipeThrough(
    new TransformStream({
      flush() {
        clearTimeout(bodyDeadline);
      },
    }),
  );

  return new NextResponse(body, {
    status: 200,
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': 'inline',
      // Never MIME-sniff proxied bytes into something frameable as HTML.
      'X-Content-Type-Options': 'nosniff',
      // Same-origin framing only (our own page), and short-lived caching.
      'X-Frame-Options': 'SAMEORIGIN',
      'Content-Security-Policy': "frame-ancestors 'self'",
      'Cache-Control': 'public, max-age=3600',
    },
  });
}
