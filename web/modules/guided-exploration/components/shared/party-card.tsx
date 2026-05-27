'use client';

import { useContextParty } from '@/components/providers/context-provider';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import Image from 'next/image';
import type { ReactNode } from 'react';
import { useState } from 'react';

interface PartyCardProps {
  /** Party identifier (e.g., 'spd', 'cdu') */
  partyId: string;
  /** Content to render inside the card */
  children: ReactNode;
  /** Whether this section is still streaming */
  isStreaming?: boolean;
  className?: string;
}

/**
 * Card component for displaying party-specific content with logo.
 * Accessibility: the card is a plain container (no landmark) so screen readers
 * read it as the party-name heading (h3) followed by the content, instead of
 * announcing a redundant "Position der …" region first.
 */
export function PartyCard({
  partyId,
  children,
  isStreaming,
  className,
}: PartyCardProps) {
  const [imageError, setImageError] = useState(false);
  const normalizedPartyId = partyId.toLowerCase();
  const partyDetails = useContextParty(normalizedPartyId);
  const imageUrl = buildPartyImageUrl(normalizedPartyId);
  const displayName = partyDetails?.name ?? partyId.toUpperCase();
  const partyColor = partyDetails?.background_color ?? '#6B7280';

  return (
    // Plain container (not a landmark): a named <section> would expose a
    // "Position der …" region that SR users hear before the h3, duplicating
    // the party name. We let the h3 heading + content carry the semantics.
    <div
      className={cn(
        'relative rounded-lg border bg-card',
        isStreaming && 'border-dashed',
        className,
      )}
    >
      {/* Party header with logo */}
      <div className="flex items-center gap-2 border-b px-3 py-2">
        {/* Party logo with party color background */}
        <div
          className="flex size-7 shrink-0 items-center justify-center rounded p-0.5"
          style={{ backgroundColor: partyColor }}
        >
          {imageError ? (
            <span className="text-[10px] font-semibold text-white">
              {partyId.toUpperCase().slice(0, 3)}
            </span>
          ) : (
            <Image
              src={imageUrl}
              alt="" // Decorative, name is in text
              width={24}
              height={24}
              className="object-contain"
              onError={() => setImageError(true)}
            />
          )}
        </div>

        {/* Party name as a real heading (h3, under the message's h2) so SR
            users can jump card-to-card with the headings command. */}
        <h3 className="text-base font-bold text-foreground">{displayName}</h3>

        {/* Streaming indicator */}
        {isStreaming && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-foreground">
            <span className="size-1.5 animate-pulse rounded-full bg-primary" />
            <span className="sr-only">Wird geladen</span>
          </span>
        )}
      </div>

      {/* Content area */}
      <div className="px-3 py-2">{children}</div>
    </div>
  );
}
