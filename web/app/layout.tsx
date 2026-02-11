import { AnonymousAuthProvider } from '@/components/anonymous-auth';
import { Toaster } from '@/components/ui/sonner';

import AuthServiceWorkerProvider from '@/components/providers/auth-service-worker-provider';
import { ThemeProvider } from '@/components/providers/theme-provider';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Analytics } from '@vercel/analytics/react';
import type { Metadata, Viewport } from 'next';
import './globals.css';
import TenantProvider from '@/components/providers/tenant-provider';
import { TENANT_ID_HEADER } from '@/lib/constants';
import { getTenant } from '@/lib/firebase/firebase-admin';
import { getUser } from '@/lib/firebase/firebase-server';
import { productionRobots } from '@/lib/seo';
import { IS_EMBEDDED } from '@/lib/utils';
import { LazyMotion, domAnimation } from 'motion/react';
import { headers } from 'next/headers';

export const metadata: Metadata = {
  metadataBase: new URL('https://wahl.chat'),
  title: {
    default: 'wahl.chat - Politik interaktiv verstehen',
    template: '%s | wahl.chat',
  },
  description:
    'Verstehe die Positionen der Parteien zu Bundestags-, Landtags- und Kommunalwahlen. Unterhalte dich bei wahl.chat mit den Programmen der Parteien, stelle Fragen zu deinen Themen und lass Parteipositionen kritisch einordnen.',
  applicationName: 'wahl.chat',
  keywords: [
    'Wahl Chat',
    'Wahl',
    'Chat',
    'AI Wahl Chat',
    'AI Wahlprogramm',
    'KI Chat',
    'KI Wahlprogramm',
    'Wahlprogramm',
    'Parteien',
    'Politik',
    'Politik verstehen',
    'Bundestagswahl',
    'Bundestagswahl 2025',
    'Landtagswahl',
    'Kommunalwahl',
    'Landtagswahl 2026',
    'Kommunalwahl 2026',
    'AI',
    'KI',
    'Künstliche Intelligenz',
    'Chatbot',
    'Chat',
    'Deutschland',
    'Deutschlandpolitik',
    'KI Wahlhilfe',
    'KI Wahl',
    'Wahl KI',
    'Wahlentscheidung Hilfe',
    'Wahl informieren',
    'Wahlcheck',
    'Wahl-o-Mat',
    'Wahl-o-Mat Alternative',
  ],
  robots: productionRobots,
  openGraph: {
    title: {
      default: 'wahl.chat - Politik interaktiv verstehen',
      template: '%s | wahl.chat - Politik interaktiv verstehen',
    },
    description:
      'Verstehe die Positionen der Parteien zu Bundestags-, Landtags- und Kommunalwahlen. Unterhalte dich bei wahl.chat mit den Programmen der Parteien, stelle Fragen zu deinen Themen und lass Parteipositionen kritisch einordnen.',
    images: ['https://wahl.chat/images/logo.webp'],
    url: 'https://wahl.chat',
    siteName: 'wahl.chat',
    locale: 'de-DE',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    site: '@wahl_chat',
    creator: '@wahl_chat',
    title: 'wahl.chat - Politik interaktiv verstehen',
    description:
      'Verstehe die Positionen der Parteien zu Bundestags-, Landtags- und Kommunalwahlen. Unterhalte dich bei wahl.chat mit den Programmen der Parteien, stelle Fragen zu deinen Themen und lass Parteipositionen kritisch einordnen.',
    images: ['https://wahl.chat/images/logo.webp'],
  },
};

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

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const headersList = await headers();
  const tenantId = headersList.get(TENANT_ID_HEADER);
  const tenant = await getTenant(tenantId);
  const user = await getUser();

  return (
    <html lang="de" suppressHydrationWarning>
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
                  name: 'wahl.chat',
                  url: 'https://wahl.chat',
                  description:
                    'Politische Informationsplattform – Parteipositionen interaktiv vergleichen.',
                },
                {
                  '@type': 'WebSite',
                  name: 'wahl.chat',
                  url: 'https://wahl.chat',
                  inLanguage: 'de',
                  description:
                    'Verstehe die Positionen der Parteien zu Bundestags-, Landtags- und Kommunalwahlen.',
                },
              ],
            }),
          }}
        />
      </head>
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
                  {children}
                </ThemeProvider>
                <Toaster expand duration={1500} position="top-right" />
                {/* <LoginReminderToast /> */}
                {/* TODO: implement again when problems are fixed <IframeChecker /> */}
                <Analytics />
              </LazyMotion>
            </body>
          </TenantProvider>
        </AnonymousAuthProvider>
      </TooltipProvider>
    </html>
  );
}
