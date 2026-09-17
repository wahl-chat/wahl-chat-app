import { IS_EMBEDDED } from '@/lib/utils';
import Script from 'next/script';

/** Google Ads account the campaign conversions are reported to. */
const GOOGLE_ADS_ID = 'AW-18454998566';

// Only the production deployment belongs in the ad account: previews and local
// dev would report their own traffic as campaign traffic, and the embed
// deployment (embed.wahl.chat) runs inside third-party pages that no ad points
// at.
const IS_TAG_ENABLED = process.env.VERCEL_ENV === 'production' && !IS_EMBEDDED;

// Kept as the snippet Google hands out (gtag.js loader + inline bootstrap)
// rather than a tag-manager abstraction, so the conversion tracking Google
// verifies is exactly what it expects to find.
function GoogleAdsTag() {
  if (!IS_TAG_ENABLED) {
    return null;
  }

  return (
    <>
      <Script
        src={`https://www.googletagmanager.com/gtag/js?id=${GOOGLE_ADS_ID}`}
        strategy="afterInteractive"
      />
      <Script id="google-ads-gtag" strategy="afterInteractive">
        {`window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '${GOOGLE_ADS_ID}');`}
      </Script>
    </>
  );
}

export default GoogleAdsTag;
