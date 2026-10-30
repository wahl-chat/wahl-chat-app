import { LOCALE_INFO, type Locale } from '@/i18n/locales';
import { Link } from '@/i18n/navigation';
import type { Context } from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import { formatDate } from '@/lib/utils';
import { useLocale, useTranslations } from 'next-intl';

type Props = {
  context: Context;
  parties?: PartyDetails[];
};

/** "A, B und C" / "A, B and C", joined the way the reader's language does. */
function formatPartyList(parties: PartyDetails[], locale: Locale): string {
  return new Intl.ListFormat(LOCALE_INFO[locale].intl, {
    style: 'long',
    type: 'conjunction',
  }).format(parties.map((party) => party.name));
}

function IntroLink({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className="font-medium underline">
      {children}
    </Link>
  );
}

/**
 * Crawlable prose about the election, rendered below the interactive surface.
 *
 * Placement is deliberate: search engines read the whole document regardless of
 * visual order, so the selector and chat input keep the top of the page while
 * the page still carries enough text to be understood as being about this
 * election.
 */
function ContextIntro({ context, parties }: Props) {
  const t = useTranslations('home.contextIntro');
  const locale = useLocale();
  const electionDate = formatDate(context.date, locale);
  const partyList = parties?.length
    ? formatPartyList(parties, locale)
    : undefined;

  return (
    <section className="mt-8 space-y-4 text-sm text-muted-foreground">
      <h2 className="text-xl font-bold text-foreground md:text-2xl">
        {t('heading', { name: context.name })}
      </h2>

      <p>
        {electionDate
          ? t('introWithDate', {
              date: electionDate,
              location: context.location_name,
            })
          : t('introWithoutDate', { location: context.location_name })}
      </p>

      {partyList && (
        <p>{t('parties', { name: context.name, parties: partyList })}</p>
      )}

      <p>
        {t.rich('sources', {
          link: (chunks) => (
            <IntroLink href={`/${context.context_id}/sources`}>
              {chunks}
            </IntroLink>
          ),
        })}
      </p>

      <p>
        {t.rich('wahlOMat', {
          link: (chunks) => <IntroLink href="/how-to">{chunks}</IntroLink>,
        })}
      </p>

      <p>
        {t.rich('disclaimer', {
          link: (chunks) => <IntroLink href="/datenschutz">{chunks}</IntroLink>,
        })}
      </p>
    </section>
  );
}

export default ContextIntro;
