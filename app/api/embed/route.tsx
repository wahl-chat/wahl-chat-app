'use server';

import { track } from '@vercel/analytics/server';
import { type NextRequest, NextResponse } from 'next/server';

const SPECIAL_TENANT_ID = 'special-tenant-id';

export async function GET(request: NextRequest) {
  const tenantId = request.nextUrl.searchParams.get('tenant_id');
  const partyIds = request.nextUrl.searchParams.getAll('party_id');

  const url = new URL('https://embed.wahl.chat', request.url);

  if (tenantId === SPECIAL_TENANT_ID) {
    track('embed', {
      tenant_id: tenantId,
    });

    return NextResponse.redirect(url);
  }

  if (partyIds.length > 0) {
    url.pathname = '/session';
  }

  partyIds.forEach((partyId) => {
    url.searchParams.append('party_id', partyId);
  });

  if (tenantId) {
    url.searchParams.append('tenant_id', tenantId);

    track('embed', {
      tenant_id: tenantId,
      partyIds: partyIds?.join(','),
    });
  }

  return NextResponse.redirect(url);
}
