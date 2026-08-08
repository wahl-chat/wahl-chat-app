import type { SerializableFirebaseUser } from '@/components/anonymous-auth';
import type { PartyDetails } from '@/lib/party-details';
import { type ClassValue, clsx } from 'clsx';
import type { User } from 'firebase/auth';
import type { Timestamp } from 'firebase/firestore';
import { twMerge } from 'tailwind-merge';
import { GROUP_PARTY_ID } from './constants';

export const IS_EMBEDDED = process.env.IS_EMBEDDED === 'true';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const keyStr =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';

export function triplet(e1: number, e2: number, e3: number) {
  return (
    keyStr.charAt(e1 >> 2) +
    keyStr.charAt(((e1 & 3) << 4) | (e2 >> 4)) +
    keyStr.charAt(((e2 & 15) << 2) | (e3 >> 6)) +
    keyStr.charAt(e3 & 63)
  );
}

function rgbDataURL(r: number, g: number, b: number) {
  return `data:image/gif;base64,R0lGODlhAQABAPAA${
    triplet(0, r, g) + triplet(b, 255, 255)
  }/yH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==`;
}

function hexToRgb(hex: string) {
  const cleanedHex = hex.replace('#', '');

  const r = Number.parseInt(cleanedHex.substring(0, 2), 16);
  const g = Number.parseInt(cleanedHex.substring(2, 4), 16);
  const b = Number.parseInt(cleanedHex.substring(4, 6), 16);

  return { r, g, b };
}

export function hexDataURL(hex: string) {
  const { r, g, b } = hexToRgb(hex);
  return rgbDataURL(r, g, b);
}

export function prettifiedUrlName(url: string) {
  const regex = /https?:\/\/(?:www\.)?(?<domain>[^\/]+\.[a-z]+)/;
  const match = url.match(regex);

  if (match?.groups) {
    return match.groups.domain;
  } else {
    return url;
  }
}

export function prettifiedShortSourceName(source: string): string {
  const shortenings: { [key: string]: string } = {
    Entwurf: 'Entw.',
    Regierungsprogramm: 'Prg.',
    Wahlprogramm: 'Wahlpr.',
  };

  return source
    .split(' ')
    .map((word) => shortenings[word] || word)
    .join(' ');
}

export function generateUuid() {
  return crypto.randomUUID();
}

export function firestoreTimestampToDate(
  timestamp: Timestamp | Date | string | number | undefined | null,
): Date | undefined {
  if (!timestamp) {
    return undefined;
  }

  if (timestamp instanceof Date) {
    return timestamp;
  }

  // Handle Firestore Timestamp objects
  if (typeof timestamp === 'object' && 'toDate' in timestamp) {
    return timestamp.toDate();
  }

  // Handle string or number timestamps
  if (typeof timestamp === 'string' || typeof timestamp === 'number') {
    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? undefined : date;
  }

  return undefined;
}

export function areSetsEqual(set1: Set<string>, set2: Set<string>): boolean {
  if (set1.size !== set2.size) return false;
  return [...set1].every((item) => set2.has(item));
}

/**
 * Shuffles an array randomly using the sort-based shuffle algorithm.
 * Note: This is not a perfectly uniform shuffle, but is sufficient for UI randomization.
 */
export function shuffleArray<T>(array: T[]): T[] {
  return [...array].sort(() => Math.random() - 0.5);
}

export function prettyDate(
  dateString: string,
  format: 'full' | 'long' | 'medium' | 'short' = 'long',
): string {
  const date = new Date(dateString);

  const options: Intl.DateTimeFormatOptions = {
    dateStyle: format,
  };

  return new Intl.DateTimeFormat('en-DE', options).format(date);
}

export function formatGermanDate(
  dateString: string | null | undefined,
  format: 'full' | 'long' | 'medium' | 'short' = 'long',
): string | null {
  if (!dateString || dateString.length === 0) return null;

  const date = new Date(dateString);

  if (!date) {
    return null;
  }

  const options: Intl.DateTimeFormatOptions = {
    dateStyle: format,
  };

  return new Intl.DateTimeFormat('de-DE', options).format(date);
}

export async function generateOgImageUrl(sessionType: string) {
  if (sessionType === GROUP_PARTY_ID) {
    return;
  }

  let party: PartyDetails | undefined;
  try {
    const response = await fetch(`${process.env.SITE_URL}/api/parties`);
    if (!response.ok) {
      throw new Error('Failed to fetch parties');
    }

    const parties = await response.json();

    party = parties.find((p: PartyDetails) => p.party_id === sessionType);
  } catch (error) {
    console.error(error);
  }

  if (!party) {
    return;
  }

  const url = new URL(process.env.SITE_URL ?? 'https://wahl.chat');
  const imageUrl = new URL('/api/og', url);
  imageUrl.searchParams.set(
    'partyImageUrl',
    `${process.env.SITE_URL ?? 'https://wahl.chat'}${buildPartyImageUrl(
      party.party_id,
    )}`,
  );
  imageUrl.searchParams.set(
    'backgroundColor',
    party.background_color ?? '#fff',
  );

  return imageUrl.toString();
}

export function buildPartyImageUrl(partyId: string) {
  return `/images/${partyId}.webp`;
}

export type UserDetails = {
  photoURL?: string;
  displayName?: string;
  email?: string;
  isAnonymous: boolean;
};

export function getUserDetailsFromUser(
  user?: SerializableFirebaseUser,
): UserDetails {
  const details: UserDetails = {
    isAnonymous: true,
  };

  if (!user) return details;

  details.isAnonymous = user.isAnonymous;

  user.providerData.forEach((provider) => {
    details.photoURL ??= provider.photoURL ?? undefined;
    details.displayName ??= provider.displayName ?? undefined;
    details.email ??= provider.email ?? undefined;
  });

  return details;
}

export function makeFirebaseUserSerializable(
  user: User,
): SerializableFirebaseUser {
  return {
    displayName: user.displayName,
    email: user.email,
    phoneNumber: user.phoneNumber,
    photoURL: user.photoURL,
    providerId: user.providerId,
    uid: user.uid,
    emailVerified: user.emailVerified,
    isAnonymous: user.isAnonymous,
    providerData: user.providerData,
    metadata: {
      creationTime: user.metadata.creationTime,
      lastSignInTime: user.metadata.lastSignInTime,
    },
  };
}

/**
 * Parse the media-fragment start time (`#t=<seconds>`) from a source URL.
 * Returns the seconds as a number, or null when the URL carries no timestamp
 * (e.g. a manifesto PDF or a DIP protocol link).
 */
export function videoTimestampSeconds(url: string | undefined): number | null {
  if (!url) {
    return null;
  }
  const match = url.match(/#t=([\d.]+)/);
  if (!match) {
    return null;
  }
  const seconds = Number.parseFloat(match[1]);
  return Number.isFinite(seconds) ? seconds : null;
}

/** Format seconds as `m:ss` (e.g. 87.5 -> "1:27"). */
export function formatTimestamp(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Badge label for a source row: a video label (`▶ 1:27` / `▶ Video`) when the
 * source actually OPENS as a video, otherwise the page label (`S. N`).
 *
 * Derived from `getSourceMediaLinks` (the same helper the row uses to decide how
 * to open) so the badge can never disagree with what a click does — a video that
 * lives in `video_url`, or a `.mp4` with no `#t=` fragment, no longer mislabels
 * itself as "S. N".
 */
export function sourceBadgeLabel(source: {
  url?: string;
  video_url?: string;
  pdf_url?: string;
  page: number;
  page_label?: string;
}): string {
  const primary = getSourceMediaLinks(source)[0];
  if (primary?.kind === 'video') {
    return primary.label;
  }
  // Prefer the printed page the citation text cites (speech transcripts);
  // `page` is the physical PDF page for the viewer jump, which differs when
  // the PDF has front matter.
  return `S. ${source.page_label ?? source.page}`;
}

/** True when a URL is a playable video (a `#t=` deep-link or a `.mp4` file). */
export function isVideoUrl(url: string | undefined): boolean {
  if (!url) {
    return false;
  }
  const lower = url.toLowerCase();
  return (
    url.includes('#t=') ||
    lower.endsWith('.mp4') ||
    lower.includes('.mp4#') ||
    lower.includes('.mp4?')
  );
}

/** True when a URL points at a PDF file (ignoring any query/hash). */
export function isPdfUrl(url: string | undefined): boolean {
  if (!url) {
    return false;
  }
  const path = url.split(/[?#]/)[0].toLowerCase();
  return path.endsWith('.pdf');
}

// Hosts we can safely fetch through the same-origin PDF proxy for in-page
// viewing. Fixed allowlist of trusted public institutions (Bundestag document
// server + abgeordnetenwatch). SINGLE source of truth — the /api/pdf-proxy route
// imports this same Set, so the client-side "is proxyable" check and the
// server-side allow decision can never drift. Any PDF whose host is not listed
// falls back to opening in a new tab.
export const PROXYABLE_PDF_HOSTS = new Set<string>([
  'dserver.bundestag.de',
  'www.abgeordnetenwatch.de',
  'abgeordnetenwatch.de',
]);

/**
 * True when a PDF URL's host is on the in-page-viewer proxy allowlist AND it is
 * https. The proxy route rejects non-https URLs with a raw 400, so letting an
 * `http://` source pass here would frame that raw English error instead of the
 * German framed fallback — mirror the server's protocol check client-side.
 */
export function isProxyablePdfHost(url: string | undefined): boolean {
  if (!url) {
    return false;
  }
  try {
    const parsed = new URL(url);
    return (
      parsed.protocol === 'https:' && PROXYABLE_PDF_HOSTS.has(parsed.hostname)
    );
  } catch {
    return false;
  }
}

/** Same-origin proxy URL that streams an allowlisted PDF for in-page framing. */
export function pdfProxyUrl(url: string): string {
  return `/api/pdf-proxy?url=${encodeURIComponent(url)}`;
}

export type SourceMediaKind = 'video' | 'pdf';
export type SourceMediaLink = {
  kind: SourceMediaKind;
  url: string;
  label: string;
};

type SourceLinkFields = {
  url?: string;
  video_url?: string;
  pdf_url?: string;
};

/**
 * The format links a source exposes, in display order (video first).
 *
 * A merged speech carries both `video_url` and `pdf_url` → two links (the dual
 * quick-links). A source with neither explicit field falls back to classifying
 * its single `url` (manifesto/DIP PDFs, op videos). A plain weblink yields no
 * media link (the caller opens it in a new tab instead).
 */
export function getSourceMediaLinks(
  source: SourceLinkFields,
): SourceMediaLink[] {
  const links: SourceMediaLink[] = [];
  if (source.video_url) {
    links.push({
      kind: 'video',
      url: source.video_url,
      label: videoLinkLabel(source.video_url),
    });
  }
  if (source.pdf_url) {
    links.push({ kind: 'pdf', url: source.pdf_url, label: 'PDF' });
  }
  if (links.length === 0 && source.url) {
    if (isVideoUrl(source.url)) {
      links.push({
        kind: 'video',
        url: source.url,
        label: videoLinkLabel(source.url),
      });
    } else if (isPdfUrl(source.url)) {
      links.push({ kind: 'pdf', url: source.url, label: 'PDF' });
    }
  }
  return links;
}

function videoLinkLabel(url: string): string {
  const ts = videoTimestampSeconds(url);
  return ts !== null ? `▶ ${formatTimestamp(ts)}` : '▶ Video';
}
