import { cn } from '@/lib/utils';

/**
 * The three numbers worth stating plainly.
 *
 * The two usage figures are maintained by hand — nothing in the app exposes an
 * aggregate the frontend could read (Vercel Analytics is write-only, and there
 * is no counter document in Firestore), so they cannot self-update. Keep them
 * here, together, and refresh them deliberately rather than scattering
 * hardcoded numbers through the page.
 *
 * The election count is derived from the live contexts instead, so it stays
 * true on its own as elections are added or retired.
 */

// Last reviewed: 10 September 2026.
const USAGE_STATS = [
  { value: '400.000+', label: 'Nutzerinnen und Nutzer' },
  { value: '1 Mio.+', label: 'beantwortete Fragen' },
];

type Props = {
  electionCount: number;
};

function LandingStats({ electionCount }: Props) {
  // Dropped rather than shown as "0+" when the context read comes back empty,
  // which is the state the whole page degrades to if Firestore is unavailable.
  const stats =
    electionCount > 0
      ? [
          ...USAGE_STATS,
          { value: `${electionCount}+`, label: 'unterstützte Wahlen' },
        ]
      : USAGE_STATS;

  return (
    <dl
      className={cn(
        'grid gap-4 text-center',
        stats.length === 3 ? 'grid-cols-3' : 'grid-cols-2',
      )}
    >
      {stats.map((stat) => (
        <div key={stat.label} className="flex flex-col gap-1">
          <dt className="sr-only">{stat.label}</dt>
          <dd className="flex flex-col gap-1">
            <span className="text-xl font-bold tracking-tight text-foreground sm:text-2xl md:text-3xl">
              {stat.value}
            </span>
            <span className="text-pretty text-xs text-muted-foreground sm:text-sm">
              {stat.label}
            </span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default LandingStats;
