'use client';

import type { PartyDetails } from '@/lib/party-details';
import { buildPartyImageUrl, cn, hexDataURL } from '@/lib/utils';
import { CheckIcon } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';
import { Button } from './ui/button';

type Props = {
  id: string;
  party: PartyDetails;
  isSelected?: boolean;
  onPartyClicked?: (partyId: string) => void;
  selectable?: boolean;
  contextId?: string;
};

function PartyCard({
  id,
  party: { name, background_color },
  isSelected,
  onPartyClicked,
  selectable = true,
  contextId,
}: Props) {
  const [isHovered, setIsHovered] = useState(false);

  const partyImage = (
    <Image
      alt=""
      aria-hidden="true"
      blurDataURL={hexDataURL(background_color ?? '#CBD5E1')}
      src={buildPartyImageUrl(id)}
      placeholder="blur"
      sizes="20vw"
      className="object-contain p-[20%]"
      fill
    />
  );

  const sessionPath = contextId
    ? `/${contextId}/session?party_id=${id}`
    : `/session?party_id=${id}`;

  const ariaLabel = selectable
    ? `${name}${isSelected ? ' (ausgewählt)' : ''}`
    : `Chat mit ${name} starten`;

  return (
    <Button
      className={cn(
        'flex aspect-square items-center justify-center transition-all relative',
        'bg-slate-300 w-full h-fit hover:bg-slate-300 border border-muted-foreground/20 overflow-hidden',
      )}
      style={{
        backgroundColor: isHovered
          ? `color-mix(in srgb, ${background_color ?? '#e4e4e8'} 85%, black)`
          : (background_color ?? '#d4d4d8'),
        boxShadow: isSelected
          ? `0 0 0 2px color-mix(in srgb, ${
              background_color ?? '#d4d4d8'
            } 60%, black)`
          : 'none',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={selectable ? () => onPartyClicked?.(id) : undefined}
      asChild={!selectable}
      aria-label={ariaLabel}
      aria-pressed={selectable ? isSelected : undefined}
    >
      {selectable ? (
        <>
          <div
            className={cn(
              'absolute top-2 right-2 bg-zinc-800 border border-zinc-700 rounded-full p-[2px] transition-all duration-100 ease-in-out',
              isSelected ? 'opacity-100 scale-100' : 'opacity-0 scale-75',
            )}
            aria-hidden="true"
          >
            <CheckIcon className="size-2 text-white" />
          </div>
          {partyImage}
        </>
      ) : (
        <Link
          href={sessionPath}
          onClick={() => onPartyClicked?.(id)}
          aria-label={ariaLabel}
        >
          {partyImage}
        </Link>
      )}
    </Button>
  );
}

export default PartyCard;
