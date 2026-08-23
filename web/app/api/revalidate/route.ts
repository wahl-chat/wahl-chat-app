import { timingSafeEqual } from 'node:crypto';
import { revalidatePath, revalidateTag } from 'next/cache';
import { headers } from 'next/headers';
import type { NextRequest } from 'next/server';

const REVALIDATE_SECRET = process.env.REVALIDATE_SECRET;

function collectStrings(single: unknown, many: unknown): string[] {
  const values = [
    ...(typeof single === 'string' ? [single] : []),
    ...(Array.isArray(many) ? many : []),
  ];
  return values.filter(
    (value): value is string => typeof value === 'string' && value.length > 0,
  );
}

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

    const body = await request.json();
    const tags = collectStrings(body.tag, body.tags);
    const paths = collectStrings(body.path, body.paths);

    if (tags.length === 0 && paths.length === 0) {
      return new Response('Bad Request: Provide tag(s) or path(s)', {
        status: 400,
      });
    }

    // layout so a context root also busts the ISR page that embeds parties.
    for (const path of paths) {
      revalidatePath(path, 'layout');
    }
    for (const tag of tags) {
      revalidateTag(tag);
    }

    return Response.json({ revalidated: { tags, paths } }, { status: 200 });
  } catch (error) {
    console.error('Revalidation error:', error);
    return new Response('Internal Server Error', { status: 500 });
  }
}
