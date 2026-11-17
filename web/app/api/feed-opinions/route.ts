import { isFeedItemId, parseFeedOpinionBody } from '@/lib/daily/opinions';
import {
  applyFeedOpinion,
  readFeedOpinionCounts,
  withdrawFeedOpinions,
} from '@/lib/firebase/feed-opinions-admin';
import { verifyFirebaseIdToken } from '@/lib/firebase/page-visit-admin';
import { type NextRequest, NextResponse } from 'next/server';

/** The caller's uid from their Firebase ID token, or null when the token is
 * missing or does not verify. Anonymous users have a uid too. */
async function callerUid(request: NextRequest): Promise<string | null> {
  const token = request.headers
    .get('authorization')
    ?.match(/^Bearer (.+)$/)?.[1];
  if (!token) {
    return null;
  }
  try {
    return (await verifyFirebaseIdToken(token)).uid;
  } catch {
    return null;
  }
}

const UNAUTHORIZED = () =>
  NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

/** An item's counts, withheld where too few readers answered. Served here
 * rather than read from Firestore, so a client never sees a raw count. */
export async function GET(request: NextRequest) {
  try {
    const uid = await callerUid(request);
    if (!uid) {
      return UNAUTHORIZED();
    }
    const itemId = request.nextUrl.searchParams.get('item_id');
    if (!itemId || !isFeedItemId(itemId)) {
      return NextResponse.json({ error: 'Invalid item_id' }, { status: 400 });
    }
    return NextResponse.json(
      { counts: await readFeedOpinionCounts(itemId) },
      { headers: { 'cache-control': 'no-store' } },
    );
  } catch (error) {
    console.error('Failed to read feed opinion counts', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}

/** Sets or takes back one opinion on a feed item; returns the item's counts. */
export async function POST(request: NextRequest) {
  try {
    const uid = await callerUid(request);
    if (!uid) {
      return UNAUTHORIZED();
    }
    const parsed = parseFeedOpinionBody(await request.json().catch(() => null));
    if (!parsed.ok) {
      return NextResponse.json({ error: parsed.error }, { status: 400 });
    }
    const result = await applyFeedOpinion(uid, parsed.data);
    if (!result.ok) {
      return NextResponse.json(
        { error: result.error },
        { status: result.error === 'consent_required' ? 409 : 404 },
      );
    }
    return NextResponse.json({ counts: result.counts });
  } catch (error) {
    console.error('Failed to store feed opinion', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}

/** Withdraws consent: deletes all of the caller's opinions. */
export async function DELETE(request: NextRequest) {
  try {
    const uid = await callerUid(request);
    if (!uid) {
      return UNAUTHORIZED();
    }
    const deleted = await withdrawFeedOpinions(uid);
    return NextResponse.json({ deleted });
  } catch (error) {
    console.error('Failed to withdraw feed opinions', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}
