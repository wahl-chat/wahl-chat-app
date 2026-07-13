import { type NextRequest, NextResponse } from 'next/server';

// FIX 13: Prevent Vercel from truncating long SSE streams (default 10s too short).
export const maxDuration = 300;

/**
 * POST /api/pro-con
 *
 * Proxies the request to the FastAPI backend SSE pro-con endpoint
 * (POST /api/v1/pro-con) and streams the response back to the browser.
 *
 * The pro-con flow is NOT a useChat turn — it is consumed via
 * fetch + ReadableStream in generate-pro-con-perspective.ts (D-05).
 *
 * Security: only forwards to the configured backend URL (env var); never
 * echoes an arbitrary upstream URL from the request (T-07-02).
 */
export async function POST(request: NextRequest) {
  const backendUrl =
    process.env.API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080';

  const targetUrl = `${backendUrl}/api/v1/pro-con`;

  let body: string;
  try {
    body = await request.text();
  } catch {
    return new NextResponse('Bad Request', { status: 400 });
  }

  const upstream = await fetch(targetUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body,
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
