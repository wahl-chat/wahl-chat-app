import DonationDialog from '@/components/donation-dialog';
import { Button } from '@/components/ui/button';
import { Link } from '@/i18n/navigation';
import { localeAlternates, resolveLocale } from '@/lib/seo';
import { HeartHandshakeIcon } from 'lucide-react';
import type { Metadata } from 'next';
import { useTranslations } from 'next-intl';
import { getTranslations } from 'next-intl/server';
import Image from 'next/image';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const locale = resolveLocale((await params).locale);
  const t = await getTranslations({ locale, namespace: 'meta.aboutUs' });
  return {
    title: t('title'),
    description: t('description'),
    alternates: localeAlternates('/about-us', locale),
  };
}

const siteLink = (chunks: React.ReactNode) => (
  <Link href="http://wahl.chat/">{chunks}</Link>
);

/** The address is also the link text, so the message carries it once. */
function emailLink(address: string) {
  return function EmailLink(chunks: React.ReactNode) {
    return <a href={`mailto:${address}`}>{chunks}</a>;
  };
}

function AboutUs() {
  const t = useTranslations('about');

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center justify-center space-y-6 pt-4">
      <div className="relative aspect-[4/3] w-full">
        <Image
          src="/images/team.webp"
          alt={t('teamImageAlt')}
          fill
          sizes="(max-width: 768px) 100vw, 75vw"
          className="object-cover"
        />
      </div>
      <section className="space-y-4">
        <p>
          <span className="font-bold [&_a]:underline">
            {t.rich('founders', { link: siteLink })}{' '}
            <a href="https://www.linkedin.com/in/sebmai/" target="_blank">
              Sebastian
            </a>
            ,{' '}
            <a href="https://www.linkedin.com/in/antonwy/" target="_blank">
              Anton
            </a>
            ,{' '}
            <a
              href="https://www.linkedin.com/in/michel-schimpf-55069b198/"
              target="_blank"
            >
              Michel
            </a>
            ,{' '}
            <a href="https://www.linkedin.com/in/robin-frasch/" target="_blank">
              Robin
            </a>
            ,{' '}
            <a href="https://www.linkedin.com/in/roman-mayr/" target="_blank">
              Roman
            </a>{' '}
          </span>
          {t('foundersCaption')}
        </p>

        <p>{t('story')}</p>
        <p className="[&_a]:underline">
          {t.rich('studentTeam', {
            link: (chunks) => (
              <Link href="https://tum-socialaiclub.de">{chunks}</Link>
            ),
          })}{' '}
          <a
            href="https://www.linkedin.com/in/annika-siefke-424655226/"
            target="_blank"
          >
            Annika
          </a>
          ,{' '}
          <a
            href="https://www.linkedin.com/in/miquel-camprubi-bonet/"
            target="_blank"
          >
            Miquel
          </a>
          ,{' '}
          <a
            href="https://www.linkedin.com/in/david-vogenauer/"
            target="_blank"
          >
            David
          </a>
          , {t('lastName', { name: 'Simone' })}.
        </p>
        <p className="[&_a]:underline">
          {t('thanks')}{' '}
          <a target="_blank" href="https://www.linkedin.com/in/simonkaran/">
            Simon
          </a>
          ,{' '}
          <a
            target="_blank"
            href="https://www.linkedin.com/in/nathan-orester-898014247/"
          >
            Nathan
          </a>
          ,{' '}
          <a
            target="_blank"
            href="https://www.linkedin.com/in/anton-kluge-0b0aa6220/"
          >
            Anton
          </a>
          ,{' '}
          <a
            target="_blank"
            href="https://www.linkedin.com/in/paul-barbu-8391b7216/"
          >
            Paul
          </a>
          ,{' '}
          <a target="_blank" href="https://www.linkedin.com/in/etiennekoehler/">
            Etienne
          </a>
          ,{' '}
          <a target="_blank" href="https://www.linkedin.com/in/nikhil-j-roy/">
            Nikhil
          </a>
          , Mai
        </p>
        <p className="[&_a]:underline">
          {t.rich('joinTeam', {
            link: siteLink,
            email: emailLink('info@wahl.chat'),
          })}
        </p>
        <p className="[&_a]:underline">
          {t.rich('thesis', { email: emailLink('robin@wahl.chat') })}
        </p>

        <div className="flex items-center justify-between gap-4 rounded-md border border-border p-4">
          <div className="flex flex-col">
            <h2 className="font-bold">{t('supportTitle')}</h2>
            <p className="text-sm text-muted-foreground">
              {t('supportDescription')}
            </p>
          </div>

          <DonationDialog>
            <Button>
              <HeartHandshakeIcon />
              {t('donate')}
            </Button>
          </DonationDialog>
        </div>
      </section>
    </div>
  );
}

export default AboutUs;
