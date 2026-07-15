import { type NextRequest, NextResponse } from 'next/server';

// FIX 13: Prevent Vercel from truncating long SSE streams (default 10s too short).
export const maxDuration = 300;

/**
 * POST /api/voting-behavior
 *
 * Proxies the request to the FastAPI backend SSE voting-behavior endpoint
 * (POST /api/v1/voting-behavior) and streams the response back.
 *
 * Security: only forwards to the configured backend URL (env var).
 */
export async function POST(request: NextRequest) {
  const backendUrl =
    process.env.API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080';

  const targetUrl = `${backendUrl}/api/v1/voting-behavior`;

  let body: string;
  try {
    body = await request.text();
  } catch {
    return new NextResponse('Bad Request', { status: 400 });
  }

  // Forward the caller's Firebase ID token so the backend can verify
  // user_is_logged_in / premium claims (A3 contract). Absent when signed out.
  const authorization = request.headers.get('authorization');

  const upstream = await fetch(targetUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(authorization ? { Authorization: authorization } : {}),
    },
    body,
    // Propagate client aborts upstream so an abandoned stream stops burning
    // backend tokens instead of running to the 180s budget.
    signal: request.signal,
    // @ts-expect-error — Node 18+ fetch supports duplex streaming
    duplex: 'half',
  });

  if (!upstream.ok) {
    const text = await upstream.text();
    return new NextResponse(text, { status: upstream.status });
  }

  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'X-Accel-Buffering': 'no',
    },
  });
}
