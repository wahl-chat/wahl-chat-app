import { timingSafeEqual } from 'node:crypto';
import { expireAbandonedOpinions } from '@/lib/firebase/feed-opinions-admin';
import { type NextRequest, NextResponse } from 'next/server';

// Vercel Cron calls this daily (`vercel.json`) with `CRON_SECRET` as bearer.
export const maxDuration = 300;

function authorized(header: string | null, secret: string): boolean {
  const expected = Buffer.from(`Bearer ${secret}`);
  const given = Buffer.from(header ?? '');
  return given.length === expected.length && timingSafeEqual(given, expected);
}

/** Deletes the feed opinions of readers past retention. */
export async function GET(request: NextRequest) {
  const secret = process.env.CRON_SECRET;
  if (!secret) {
    console.error('CRON_SECRET is not configured');
    return NextResponse.json({ error: 'Not configured' }, { status: 500 });
  }
  if (!authorized(request.headers.get('authorization'), secret)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }
  try {
    const expired = await expireAbandonedOpinions(new Date());
    console.info('Expired feed opinions', expired);
    return NextResponse.json(expired);
  } catch (error) {
    console.error('Failed to expire feed opinions', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 },
    );
  }
}
