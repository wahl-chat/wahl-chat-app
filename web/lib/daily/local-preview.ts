import { readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import type { DailyDigest } from '@/lib/firebase/firebase.types';

/**
 * Hand-made digests for trying out content the builder does not produce yet
 * (e.g. an audio summary), shown on the local dev server only. The folder is
 * gitignored and lives under `public/` so its media files are served as-is;
 * each `*.json` file there holds one `DailyDigest`.
 */
export const LOCAL_PREVIEW_DIR = path.join(
  process.cwd(),
  'public',
  'local-preview',
);

export async function getLocalPreviewDigests(): Promise<DailyDigest[]> {
  if (process.env.NODE_ENV !== 'development') {
    return [];
  }
  let files: string[];
  try {
    files = await readdir(LOCAL_PREVIEW_DIR);
  } catch {
    return [];
  }
  const digests = await Promise.all(
    files
      .filter((file) => file.endsWith('.json'))
      .map(async (file) => {
        try {
          const raw = await readFile(
            path.join(LOCAL_PREVIEW_DIR, file),
            'utf8',
          );
          return JSON.parse(raw) as DailyDigest;
        } catch (error) {
          console.error(`[local-preview] Skipping unreadable ${file}:`, error);
          return null;
        }
      }),
  );
  return digests.filter((d): d is DailyDigest => d !== null);
}
