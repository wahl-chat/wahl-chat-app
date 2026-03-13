import { Button } from '@/components/ui/button';
import { GraduationCapIcon } from 'lucide-react';
import Link from 'next/link';

const OPEN_CALL_PATH =
  'public/additional_documents/hiring/WahlChatOpenCall.pdf';

function buildOpenCallUrl(): string | null {
  const bucket = process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET;
  if (!bucket) {
    if (process.env.NODE_ENV === 'development') {
      console.error(
        '[OpenCallCard] NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET is not set — card will not render.',
      );
    }
    return null;
  }
  const url = new URL('https://firebasestorage.googleapis.com');
  url.pathname = `/v0/b/${bucket}/o/${encodeURIComponent(OPEN_CALL_PATH)}`;
  url.searchParams.set('alt', 'media');
  return url.toString();
}

/** Server-side check: returns the URL if the document exists, null otherwise.
 *  Result is cached for 1 hour via Next.js fetch ISR. */
export async function getAvailableOpenCallUrl(): Promise<string | null> {
  const url = buildOpenCallUrl();
  if (!url) return null;
  try {
    const res = await fetch(url, {
      method: 'HEAD',
      next: { revalidate: 3600 },
    });
    return res.ok ? url : null;
  } catch {
    return null;
  }
}

function OpenCallCard({ url }: { url: string }) {
  return (
    <div className="flex flex-col rounded-md border border-border">
      <div className="flex grow flex-col justify-between p-4">
        <div>
          <h2 className="font-bold">Masterarbeiten mit Impact</h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Erforsche politische Transparenz und Fact-Checking zusammen mit Open
            Parliament TV und der University of Cambridge. Bewirb dich jetzt!
          </p>
        </div>
        <Button asChild variant="secondary" className="w-full">
          <Link href={url} target="_blank" rel="noopener noreferrer">
            <GraduationCapIcon className="size-5" />
            Open Call
          </Link>
        </Button>
      </div>
    </div>
  );
}

export default OpenCallCard;
