'use client';

import { useContextParty } from '@/components/providers/context-provider';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import type { AspectComparison } from '@/modules/guided-exploration/types';
import Image from 'next/image';
import { useState } from 'react';

interface AspectComparisonViewProps {
  comparison: AspectComparison;
  className?: string;
}

export function AspectComparisonView({
  comparison,
  className,
}: AspectComparisonViewProps) {
  if (comparison.aspects.length === 0) {
    return (
      <p className="text-sm text-foreground">
        Keine vergleichbaren Aspekte gefunden.
      </p>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {comparison.aspects.map((aspect) => (
        <section
          key={aspect.name}
          className="overflow-hidden rounded-lg border bg-card"
        >
          <header className="border-b bg-muted/40 px-4 py-2.5">
            <h3 className="text-base font-bold text-foreground">
              {aspect.name}
            </h3>
          </header>
          <div className="grid grid-cols-1 gap-2 p-3 sm:grid-cols-2">
            {aspect.partyStances.map((stance) => (
              <CompactPartyCard
                key={stance.party}
                partyId={stance.party}
                stance={stance.stance}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function CompactPartyCard({
  partyId,
  stance,
}: {
  partyId: string;
  stance: string;
}) {
  const [imageError, setImageError] = useState(false);
  const normalizedId = partyId.toLowerCase();
  const partyDetails = useContextParty(normalizedId);
  const imageUrl = buildPartyImageUrl(normalizedId);
  const displayName = partyDetails?.name ?? partyId.toUpperCase();
  const partyColor = partyDetails?.background_color ?? '#6B7280';

  return (
    <div className="overflow-hidden rounded-lg border">
      {/* Compact header */}
      <div className="flex items-center gap-2 border-b bg-muted/30 px-2.5 py-1.5">
        <div
          className="flex size-5 shrink-0 items-center justify-center rounded"
          style={{ backgroundColor: partyColor }}
        >
          {imageError ? (
            <span className="text-[7px] font-bold text-white">
              {partyId.toUpperCase().slice(0, 3)}
            </span>
          ) : (
            <Image
              src={imageUrl}
              alt=""
              width={14}
              height={14}
              className="object-contain"
              onError={() => setImageError(true)}
            />
          )}
        </div>
        <span className="text-xs font-semibold">{displayName}</span>
      </div>
      {/* Stance content */}
      <div className="px-2.5 py-2">
        <p className="text-sm text-foreground">{stance}</p>
      </div>
    </div>
  );
}
