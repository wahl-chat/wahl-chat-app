'use server';

import { track } from '@vercel/analytics/server';
import { type NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const tenantId = request.nextUrl.searchParams.get('tenant_id');

  // Embedding partners start a chat, so this lands on the chat page, not /.
  const url = new URL('/chat', request.url);

  if (tenantId) {
    url.searchParams.append('tenant_id', tenantId);

    track('quick', {
      tenant_id: tenantId,
    });
  }

  return NextResponse.redirect(url);
}
