import type { SerializableFirebaseUser } from '@/components/anonymous-auth';
import type { PartyDetails } from '@/lib/party-details';
import type { Source } from '@/lib/stores/chat-store.types';
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
  timestamp: Timestamp | Date | undefined,
) {
  if (!timestamp) {
    return;
  }

  if (timestamp instanceof Date) {
    return timestamp;
  }

  return timestamp.toDate();
}

export function areSetsEqual(set1: Set<string>, set2: Set<string>): boolean {
  if (set1.size !== set2.size) return false;
  return [...set1].every((item) => set2.has(item));
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

export function buildPdfUrl(source: Source) {
  return new URL(
    `/pdf/view?page=${encodeURIComponent(
      source.page,
    )}&pdf=${encodeURIComponent(source.url)}`,
    window.location.href,
  );
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
