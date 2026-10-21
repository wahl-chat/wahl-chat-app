import {
  upsertPageVisitFromServer,
  verifyFirebaseIdToken,
} from '@/lib/firebase/page-visit-admin';
import { parsePageVisitFlushBody } from '@/lib/page-visit/page-visit-request';
import { type NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const parsed = parsePageVisitFlushBody(body);
    if (!parsed.ok) {
      return NextResponse.json({ error: parsed.error }, { status: 400 });
    }

    const headerToken = request.headers.get('authorization')?.split(' ')[1];
    const idToken = headerToken ?? parsed.data.idToken;
    if (!idToken) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const decoded = await verifyFirebaseIdToken(idToken);
    await upsertPageVisitFromServer({
      visitId: parsed.data.visitId,
      userId: decoded.uid,
      visibleMs: parsed.data.visibleMs,
      lastPath: parsed.data.lastPath,
      landingPath: parsed.data.landingPath,
      startedAtMs: parsed.data.startedAtMs,
      contextId: parsed.data.contextId,
      tenantId: parsed.data.tenantId,
      embedded: parsed.data.embedded,
    });

    return new NextResponse(null, { status: 204 });
  } catch (error) {
    console.error('Failed to flush page visit', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}
