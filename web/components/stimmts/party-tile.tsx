import { partyLogo, partyTileClass } from '@/lib/stimmts/parties';
import { cn } from '@/lib/utils';
import Image from 'next/image';

type Props = {
  partyId: string;
  size?: 'md' | 'sm';
};

/** The party's own logo on its colour tile, as on the chamber's markers. */
function PartyTile({ partyId, size = 'md' }: Props) {
  return (
    <span
      aria-hidden
      className={cn(
        'inline-flex flex-none items-center justify-center overflow-hidden rounded-sm',
        size === 'md' ? 'h-11 w-16' : 'h-[30px] w-11',
        partyTileClass(partyId),
      )}
    >
      <Image
        src={partyLogo(partyId)}
        alt=""
        width={size === 'md' ? 54 : 38}
        height={size === 'md' ? 32 : 22}
        className="size-full max-h-[73%] max-w-[85%] object-contain"
      />
    </span>
  );
}

export default PartyTile;
