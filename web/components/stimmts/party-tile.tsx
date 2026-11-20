import { partyLogo, partyTileClass } from '@/lib/stimmts/parties';
import { cn } from '@/lib/utils';
import Image from 'next/image';

type Props = {
  partyId: string;
  /** `responsive` is `sm` on a phone and `md` from md up. */
  size?: 'md' | 'sm' | 'responsive';
  className?: string;
};

const TILE_SIZE = {
  md: 'h-11 w-16',
  sm: 'h-[30px] w-11',
  responsive: 'h-[30px] w-11 md:h-11 md:w-16',
} as const;

/** The party's own logo on its colour tile, as on the chamber's markers. */
function PartyTile({ partyId, size = 'md', className }: Props) {
  return (
    <span
      aria-hidden
      className={cn(
        'inline-flex flex-none items-center justify-center overflow-hidden rounded-sm',
        TILE_SIZE[size],
        partyTileClass(partyId),
        className,
      )}
    >
      <Image
        src={partyLogo(partyId)}
        alt=""
        width={size === 'sm' ? 38 : 54}
        height={size === 'sm' ? 22 : 32}
        className="size-full max-h-[73%] max-w-[85%] object-contain"
      />
    </span>
  );
}

export default PartyTile;
