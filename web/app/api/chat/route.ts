import { type NextRequest, NextResponse } from 'next/server';

// FIX 13: Prevent Vercel from truncating long SSE streams.
// Default function timeout (10s) is far too short for multi-party chat generation.
// 300s is the maximum allowed by Vercel Pro/Enterprise for the Node.js runtime.
// The default runtime for App Router route handlers is already 'nodejs', so no
// explicit runtime export is needed.
export const maxDuration = 300;

/**
 * POST /api/chat
 *
 * Proxies the request to the FastAPI backend SSE chat endpoint
 * (POST /api/v1/chat) and streams the response back to the browser.
 *
 * The backend produces a Vercel AI SDK data-stream (text/event-stream with
 * x-vercel-ai-ui-message-stream: v1). We forward those headers unchanged so
 * useChat can parse the stream correctly.
 *
 * Security: only forwards to the configured backend URL (env var); never
 * echoes an arbitrary upstream URL from the request.
 */

type IncomingMessage = {
  role: string;
  content?: string;
  parts?: Array<{ type: string; text?: string }>;
};

type IncomingPayload = {
  messages?: IncomingMessage[];
  session_id?: string;
  context_id?: string;
  party_ids?: string[];
  user_is_logged_in?: boolean;
  chat_history?: unknown[];
};

export async function POST(request: NextRequest) {
  const backendUrl =
    process.env.API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080';

  const targetUrl = `${backendUrl}/api/v1/chat`;

  let payload: IncomingPayload;
  try {
    payload = (await request.json()) as IncomingPayload;
  } catch {
    return new NextResponse('Bad Request', { status: 400 });
  }

  // Derive user_message from the last message with role 'user'.
  // SDK v4: text lives in content (string) or in parts[].text where part.type === 'text'.
  const messages = payload.messages ?? [];
  let userMessage: string | undefined;
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.role === 'user') {
      const content = msg.content;
      if (typeof content === 'string' && content.length > 0) {
        userMessage = content;
      } else if (Array.isArray(msg.parts)) {
        const text = msg.parts
          .filter((p) => p.type === 'text' && typeof p.text === 'string')
          .map((p) => p.text ?? '')
          .join('');
        if (text.length > 0) {
          userMessage = text;
        }
      }
      break;
    }
  }

  if (!userMessage) {
    return new NextResponse('No user message in request', { status: 400 });
  }

  // Build the backend DTO matching ChatRequestDto.
  const dto = {
    session_id: payload.session_id,
    context_id: payload.context_id,
    user_message: userMessage,
    party_ids: payload.party_ids,
    user_is_logged_in: payload.user_is_logged_in ?? false,
    chat_history: payload.chat_history ?? [],
  };

  // Forward the caller's Firebase ID token so the backend can verify
  // user_is_logged_in / premium claims. Absent when signed out.
  const authorization = request.headers.get('authorization');

  const upstream = await fetch(targetUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(authorization ? { Authorization: authorization } : {}),
    },
    body: JSON.stringify(dto),
    // Propagate client aborts upstream so an abandoned stream stops burning
    // backend tokens instead of running to the 180s budget.
    signal: request.signal,
    // Do not buffer — stream directly to the client.
    // @ts-expect-error — Node 18+ fetch supports duplex streaming
    duplex: 'half',
  });

  if (!upstream.ok) {
    const text = await upstream.text();
    return new NextResponse(text, { status: upstream.status });
  }

  // Forward the SSE stream with the required headers so useChat parses it.
  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'x-vercel-ai-ui-message-stream':
        upstream.headers.get('x-vercel-ai-ui-message-stream') ?? 'v1',
      'X-Accel-Buffering': 'no',
    },
  });
}
