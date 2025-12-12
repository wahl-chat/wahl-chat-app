import { timingSafeEqual } from 'node:crypto';
import { revalidateTag } from 'next/cache';
import { headers } from 'next/headers';
import type { NextRequest } from 'next/server';

const REVALIDATE_SECRET = process.env.REVALIDATE_SECRET;

// Constant-time comparison of strings to prevent timing attacks
function safeCompare(a: string, b: string): boolean {
  try {
    const bufA = Buffer.from(a);
    const bufB = Buffer.from(b);
    return bufA.length === bufB.length && timingSafeEqual(bufA, bufB);
  } catch {
    return false;
  }
}

export async function POST(request: NextRequest) {
  try {
    const headersList = await headers();
    const authHeader = headersList.get('Authorization');

    if (!REVALIDATE_SECRET) {
      throw new Error('REVALIDATE_SECRET is not configured');
    }

    const expectedAuth = `Bearer ${REVALIDATE_SECRET}`;
    if (!authHeader || !safeCompare(authHeader, expectedAuth)) {
      return new Response('Unauthorized', { status: 401 });
    }

    const { tag } = await request.json();

    if (!tag || typeof tag !== 'string') {
      return new Response('Bad Request: Invalid tag', { status: 400 });
    }

    revalidateTag(tag);
    return new Response('Revalidation successful', { status: 200 });
  } catch (error) {
    console.error('Revalidation error:', error);
    return new Response('Internal Server Error', { status: 500 });
  }
}
