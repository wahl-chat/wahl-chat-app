import type { Locale } from '@/i18n/locales';
import { cn } from '@/lib/utils';
import { useId } from 'react';

// Inline SVG rather than flag emoji: Windows renders those as plain letters.
// Every flag fills the same 20×14 frame, cropped to it like a postage stamp.

function Germany() {
  return (
    <svg viewBox="0 0 5 3" preserveAspectRatio="xMidYMid slice" aria-hidden>
      <rect width="5" height="1" y="0" fill="#000000" />
      <rect width="5" height="1" y="1" fill="#DD0000" />
      <rect width="5" height="1" y="2" fill="#FFCE00" />
    </svg>
  );
}

function UnitedKingdom() {
  // Clip-path ids must be unique per instance: the flag appears in the
  // trigger and in the open menu at once.
  const id = useId();
  return (
    <svg viewBox="0 0 60 30" preserveAspectRatio="xMidYMid slice" aria-hidden>
      <clipPath id={`${id}-s`}>
        <path d="M0,0 v30 h60 v-30 z" />
      </clipPath>
      <clipPath id={`${id}-t`}>
        <path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" />
      </clipPath>
      <g clipPath={`url(#${id}-s)`}>
        <path d="M0,0 v30 h60 v-30 z" fill="#012169" />
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#FFFFFF" strokeWidth="6" />
        <path
          d="M0,0 L60,30 M60,0 L0,30"
          clipPath={`url(#${id}-t)`}
          stroke="#C8102E"
          strokeWidth="4"
        />
        <path d="M30,0 v30 M0,15 h60" stroke="#FFFFFF" strokeWidth="10" />
        <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
      </g>
    </svg>
  );
}

const FLAGS: Record<Locale, () => React.JSX.Element> = {
  de: Germany,
  en: UnitedKingdom,
};

export function Flag({
  locale,
  className,
}: {
  locale: Locale;
  className?: string;
}) {
  const Svg = FLAGS[locale];
  return (
    <span
      className={cn(
        'inline-flex h-3.5 w-5 shrink-0 overflow-hidden rounded-[2px] ring-1 ring-black/10 dark:ring-white/20 [&>svg]:size-full',
        className,
      )}
    >
      <Svg />
    </span>
  );
}
