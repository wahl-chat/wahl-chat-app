import 'server-only';

import Stripe from 'stripe';

// Lazily construct the Stripe client on first use rather than at module load,
// so importing this module (e.g. during `next build` page-data collection) does
// not require STRIPE_SECRET_KEY at build time. The env check runs at request
// time, where the secret is present (prod/Vercel). Keeps the build secret-free.
let _stripe: Stripe | undefined;

export function getStripe(): Stripe {
  if (_stripe) {
    return _stripe;
  }

  const stripeSecretKey = process.env.STRIPE_SECRET_KEY;
  if (!stripeSecretKey) {
    throw new Error('STRIPE_SECRET_KEY is not set');
  }

  _stripe = new Stripe(stripeSecretKey, {
    appInfo: {
      name: 'wahl.chat',
      url: 'https://wahl.chat',
    },
  });
  return _stripe;
}
