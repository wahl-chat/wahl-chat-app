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
  { value: '400.000+', label: 'Nutzer:innen' },
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
        'grid w-full gap-0 px-5 pb-6 pt-2 sm:px-6 sm:pb-10 sm:pt-4',
        stats.length === 3 ? 'sm:grid-cols-3' : 'sm:grid-cols-2',
      )}
    >
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="flex items-center justify-between gap-4 border-b border-border/70 py-5 last:border-b-0 sm:flex-col sm:justify-center sm:gap-3 sm:border-b-0 sm:border-l sm:border-border sm:py-4 sm:first:border-l-0"
        >
          <dt className="order-2 text-right text-sm text-muted-foreground sm:text-center">
            {stat.label}
          </dt>
          <dd className="text-2xl font-semibold tracking-[-0.035em] text-foreground sm:text-3xl md:text-4xl">
            {stat.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default LandingStats;
