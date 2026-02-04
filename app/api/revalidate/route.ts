import { timingSafeEqual } from 'node:crypto';
import { revalidatePath, revalidateTag } from 'next/cache';
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

    const { tag, path } = await request.json();

    if (path && typeof path === 'string') {
      revalidatePath(path);
      return new Response(`Revalidated path: ${path}`, { status: 200 });
    }

    if (tag && typeof tag === 'string') {
      revalidateTag(tag);
      return new Response(`Revalidated tag: ${tag}`, { status: 200 });
    }

    return new Response('Bad Request: Provide tag or path', { status: 400 });
  } catch (error) {
    console.error('Revalidation error:', error);
    return new Response('Internal Server Error', { status: 500 });
  }
}
