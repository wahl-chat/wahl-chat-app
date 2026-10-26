import { AnonymousAuthProvider } from '@/components/anonymous-auth';
import { Toaster } from '@/components/ui/sonner';

import AuthServiceWorkerProvider from '@/components/providers/auth-service-worker-provider';
import { MediaViewerProvider } from '@/components/providers/media-viewer-provider';
import { ThemeProvider } from '@/components/providers/theme-provider';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Analytics } from '@vercel/analytics/react';
import type { Metadata, Viewport } from 'next';
import '../globals.css';
// pdf.js text-layer positioning for the citation PDF viewer. Imported here, NOT
// in the dynamically imported viewer chunk: CSS imported only from a
// next/dynamic(ssr:false) chunk is dropped in some dev/HMR paths, and without
// it the text layer flows below the canvas instead of overlaying it.
import 'react-pdf/dist/esm/Page/TextLayer.css';
import PageVisitProvider from '@/components/providers/page-visit-provider';
import StudyStatusProvider from '@/components/providers/study-status-provider';
import TenantProvider from '@/components/providers/tenant-provider';
import { LOCALES, LOCALE_INFO } from '@/i18n/locales';
import { routing } from '@/i18n/routing';
import { TENANT_ID_HEADER } from '@/lib/constants';
import { socialMediaConfig } from '@/lib/contact-config';
import { getTenant } from '@/lib/firebase/firebase-admin';
import { getUser } from '@/lib/firebase/firebase-server';
import {
  BASE_URL,
  ORGANIZATION_ID,
  WEBSITE_ID,
  localizedUrl,
  productionRobots,
  resolveLocale,
} from '@/lib/seo';
import { IS_EMBEDDED } from '@/lib/utils';
import { LazyMotion, domAnimation } from 'motion/react';
import { NextIntlClientProvider, hasLocale } from 'next-intl';
import { getTranslations, setRequestLocale } from 'next-intl/server';
import { headers } from 'next/headers';
import { notFound } from 'next/navigation';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const locale = resolveLocale((await params).locale);
  const t = await getTranslations({ locale, namespace: 'meta' });
  const title = t('title');
  const description = t('description');

  return {
    metadataBase: new URL('https://wahl.chat'),
    title: {
      default: title,
      template: '%s | wahl.chat',
    },
    description,
    applicationName: 'wahl.chat',
    keywords: t('keywords').split(', '),
    robots: productionRobots,
    openGraph: {
      title: {
        default: title,
        template: `%s | ${title}`,
      },
      description,
      images: ['https://wahl.chat/images/logo.webp'],
      url: localizedUrl('/', locale),
      siteName: 'wahl.chat',
      locale: LOCALE_INFO[locale].openGraph,
      alternateLocale: LOCALES.filter((l) => l !== locale).map(
        (l) => LOCALE_INFO[l].openGraph,
      ),
      type: 'website',
    },
    twitter: {
      card: 'summary_large_image',
      site: '@wahl_chat',
      creator: '@wahl_chat',
      title,
      description,
      images: ['https://wahl.chat/images/logo.webp'],
    },
  };
}

export const viewport: Viewport = {
  maximumScale: 1, // Disable auto-zoom on mobile Safari
};

const LIGHT_THEME_COLOR = 'hsl(0 0% 100%)';
const DARK_THEME_COLOR = 'hsl(240deg 10% 3.92%)';
const THEME_COLOR_SCRIPT = `\
(function() {
  var html = document.documentElement;
  var meta = document.querySelector('meta[name="theme-color"]');
  if (!meta) {
    meta = document.createElement('meta');
    meta.setAttribute('name', 'theme-color');
    document.head.appendChild(meta);
  }
  function updateThemeColor() {
    var isDark = html.classList.contains('dark');
    meta.setAttribute('content', isDark ? '${DARK_THEME_COLOR}' : '${LIGHT_THEME_COLOR}');
  }
  var observer = new MutationObserver(updateThemeColor);
  observer.observe(html, { attributes: true, attributeFilter: ['class'] });
  updateThemeColor();
})();`;

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function RootLayout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}>) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: 'meta' });
  const headersList = await headers();
  const tenantId = headersList.get(TENANT_ID_HEADER);
  const tenant = await getTenant(tenantId);
  const user = await getUser();

  return (
    <html lang={locale} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: THEME_COLOR_SCRIPT,
          }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              '@context': 'https://schema.org',
              '@graph': [
                {
                  '@type': 'Organization',
                  '@id': ORGANIZATION_ID,
                  name: 'wahl.chat',
                  url: BASE_URL,
                  logo: `${BASE_URL}/images/logo.webp`,
                  email: socialMediaConfig.email.replace('mailto:', ''),
                  description: t('organizationDescription'),
                  // sameAs is how a search engine resolves the brand to a single
                  // entity, which is what decides exact-brand queries.
                  sameAs: [
                    socialMediaConfig.instagram,
                    socialMediaConfig.linkedin,
                    socialMediaConfig.x,
                    'https://github.com/wahl-chat',
                  ],
                },
                {
                  '@type': 'WebSite',
                  '@id': WEBSITE_ID,
                  name: 'wahl.chat',
                  url: BASE_URL,
                  inLanguage: locale,
                  publisher: { '@id': ORGANIZATION_ID },
                  description: t('websiteDescription'),
                },
              ],
            }),
          }}
        />
      </head>
      <NextIntlClientProvider>
        <AuthServiceWorkerProvider />
        <TooltipProvider>
          <AnonymousAuthProvider user={user}>
            <TenantProvider tenant={tenant}>
              <body>
                <LazyMotion features={domAnimation}>
                  <ThemeProvider
                    attribute="class"
                    enableSystem={!IS_EMBEDDED}
                    disableTransitionOnChange
                  >
                    <StudyStatusProvider>
                      <MediaViewerProvider>{children}</MediaViewerProvider>
                    </StudyStatusProvider>
                  </ThemeProvider>
                  <Toaster expand duration={1500} position="top-right" />
                  {/* <LoginReminderToast /> */}
                  {/* TODO: implement again when problems are fixed <IframeChecker /> */}
                  <PageVisitProvider embedded={IS_EMBEDDED} />
                  <Analytics />
                </LazyMotion>
              </body>
            </TenantProvider>
          </AnonymousAuthProvider>
        </TooltipProvider>
      </NextIntlClientProvider>
    </html>
  );
}
