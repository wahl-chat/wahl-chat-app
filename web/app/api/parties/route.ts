import { getParties } from '@/lib/firebase/firebase-server';
import { NextResponse } from 'next/server';

export async function GET() {
  const parties = await getParties();
  return NextResponse.json(parties);
}
