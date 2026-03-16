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
}

/**
 * Small badge showing party logo with tooltip for party name.
 * Falls back to text badge if image fails to load.
 */
export function PartyBadge({ party, className }: PartyBadgeProps) {
  const [imageError, setImageError] = useState(false);
  const partyId = party.toLowerCase();
  const imageUrl = buildPartyImageUrl(partyId);

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
            className={cn(
              'inline-flex items-center justify-center rounded-md border size-8 p-1',
              className,
            )}
          >
            <Image
              src={imageUrl}
              alt={party}
              width={24}
              height={24}
              className="rounded object-contain"
              onError={() => setImageError(true)}
            />
          </span>
        </TooltipTrigger>
        <TooltipContent>
          <span>{party}</span>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
