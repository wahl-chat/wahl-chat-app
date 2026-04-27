'use client';

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import Image from 'next/image';
import { useState } from 'react';

interface PartyBadgeProps {
  party: string;
  className?: string;
  /**
   * When true, renders an inline pill (small logo + party name side by side)
   * suitable for embedding in flowing text. Default is the square logo-only
   * badge used as a card decoration.
   */
  inline?: boolean;
}

const capitalize = (s: string) =>
  s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();

/**
 * Small badge showing party logo with tooltip for party name.
 * Falls back to text badge if image fails to load.
 *
 * Two variants:
 * - default: square logo-only badge (used as a card decoration)
 * - inline:  small rounded pill with logo + name (used inline in chat text
 *            via `[PARTY_BADGE:id]` markers)
 */
export function PartyBadge({
  party,
  className,
  inline = false,
}: PartyBadgeProps) {
  const [imageError, setImageError] = useState(false);
  const partyId = party.toLowerCase();
  const imageUrl = buildPartyImageUrl(partyId);
  const displayName = capitalize(party);

  if (inline) {
    return (
      <span
        className={cn(
          'mx-0.5 inline-flex items-center gap-1 rounded-md border bg-muted px-2 py-0.5 align-middle text-sm font-medium leading-none',
          className,
        )}
      >
        {!imageError && (
          <Image
            src={imageUrl}
            alt=""
            width={16}
            height={16}
            className="size-4 rounded-sm object-contain"
            onError={() => setImageError(true)}
          />
        )}
        <span>{displayName}</span>
      </span>
    );
  }

  // Fallback to text badge if image fails
  if (imageError) {
    return (
      <span
        className={cn(
          'inline-flex items-center rounded bg-secondary px-1.5 py-0.5 text-xs font-medium text-secondary-foreground',
          className,
        )}
      >
        {party}
      </span>
    );
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            role="img"
            aria-label={displayName}
            className={cn(
              'inline-flex items-center justify-center rounded-md border size-8 p-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
              className,
            )}
          >
            <Image
              src={imageUrl}
              alt=""
              width={24}
              height={24}
              className="rounded object-contain"
              onError={() => setImageError(true)}
            />
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <span>{displayName}</span>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
