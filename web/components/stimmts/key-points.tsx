import { FOCUS_RING, SECTION_LABEL } from '@/components/daily/card-styles';
import {
  keyPointSourceAria,
  keyPointSourceLabel,
  keyPointSourceUrl,
} from '@/lib/stimmts/drucksache';
import type { KeyPoint } from '@/lib/stimmts/types';
import { cn } from '@/lib/utils';

/**
 * "Kernpunkte": three plain sentences, each followed by the Drucksache page
 * that backs it, so every claim on the front of the card is one tap from its
 * source.
 */
function KeyPoints({ points }: { points: KeyPoint[] }) {
  return (
    <>
      <p className={cn(SECTION_LABEL, 'text-[13px]')}>Kernpunkte</p>
      <ul className="flex list-disc flex-col gap-1 pl-[18px] text-[15px] leading-[21px] text-[var(--daily-body)] md:gap-2 md:text-base md:leading-6">
        {points.map((point) => (
          <li key={point.text}>
            {point.text}{' '}
            <a
              href={keyPointSourceUrl(point.source)}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={keyPointSourceAria(point.source)}
              className={cn(
                FOCUS_RING,
                'inline-flex h-5 items-center whitespace-nowrap rounded-full bg-[var(--daily-surface)] px-2 align-[1px] text-xs font-medium leading-none text-[var(--daily-ink)] transition-colors hover:bg-[var(--daily-border)]',
              )}
            >
              {keyPointSourceLabel(point.source)}
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}

export default KeyPoints;
