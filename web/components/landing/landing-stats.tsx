import LabeledDivider from '@/components/labeled-divider';
import { LOCALE_INFO } from '@/i18n/locales';
import { cn } from '@/lib/utils';
import { useLocale, useTranslations } from 'next-intl';

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
const USERS = 400_000;
const ANSWERED_QUESTIONS = 1_000_000;

type Props = {
  electionCount: number;
};

function LandingStats({ electionCount }: Props) {
  const t = useTranslations('landing.stats');
  const intl = LOCALE_INFO[useLocale()].intl;
  // "400.000" / "400,000", and "1 Mio." / "1M": the separators and the
  // abbreviation both follow the reader's language.
  const plain = new Intl.NumberFormat(intl);
  const compact = new Intl.NumberFormat(intl, { notation: 'compact' });

  const usageStats = [
    {
      value: t('atLeast', { value: plain.format(USERS) }),
      label: t('users'),
    },
    {
      value: t('atLeast', { value: compact.format(ANSWERED_QUESTIONS) }),
      label: t('answeredQuestions'),
    },
  ];

  // Dropped rather than shown as "0+" when the context read comes back empty,
  // which is the state the whole page degrades to if Firestore is unavailable.
  const stats =
    electionCount > 0
      ? [
          ...usageStats,
          {
            value: t('atLeast', { value: plain.format(electionCount) }),
            label: t('supportedElections'),
          },
        ]
      : usageStats;

  return (
    <div className="flex w-full flex-col items-center gap-4">
      <LabeledDivider>{t('heading')}</LabeledDivider>

      <dl
        className={cn(
          'grid w-full gap-4 text-center',
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
    </div>
  );
}

export default LandingStats;
