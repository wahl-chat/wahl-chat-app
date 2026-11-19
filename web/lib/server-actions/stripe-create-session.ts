'use server';

import type { Stripe } from 'stripe';

import { getLocale, getTranslations } from 'next-intl/server';
import { headers } from 'next/headers';

import { getPathname } from '@/i18n/navigation';
import { getStripe } from '@/lib/stripe/stripe';
import { CURRENCY } from '@/lib/stripe/stripe-config';
import { formatAmountForStripe } from '@/lib/stripe/stripe-helpers';

export async function createCheckoutSession(
  data: FormData,
): Promise<{ client_secret: string | null; url: string | null }> {
  const amountString = data.get('amount');

  if (!amountString) {
    throw new Error('Amount is required');
  }

  const amount = Number(amountString);

  const headersStore = await headers();

  const origin: string = headersStore.get('origin') as string;

  // The checkout page and the pages Stripe sends the donor back to follow the
  // language they donated in.
  const locale = await getLocale();
  const t = await getTranslations('donate');
  const resultPath = getPathname({ href: '/donate/result', locale });
  const donatePath = getPathname({ href: '/donate', locale });

  const checkoutSession: Stripe.Checkout.Session =
    await getStripe().checkout.sessions.create({
      mode: 'payment',
      submit_type: 'donate',
      line_items: [
        {
          quantity: 1,
          price_data: {
            currency: CURRENCY,
            product_data: {
              name: t('productName'),
            },
            unit_amount: formatAmountForStripe(amount, CURRENCY),
          },
        },
      ],
      success_url: `${origin}${resultPath}?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}${donatePath}`,
      locale,
      ui_mode: 'hosted',
    });

  return {
    client_secret: checkoutSession.client_secret,
    url: checkoutSession.url,
  };
}

export async function createPaymentIntent(
  data: FormData,
): Promise<{ client_secret: string }> {
  const paymentIntent: Stripe.PaymentIntent =
    await getStripe().paymentIntents.create({
      amount: formatAmountForStripe(
        Number(data.get('customDonation') as string),
        CURRENCY,
      ),
      automatic_payment_methods: { enabled: true },
      currency: CURRENCY,
    });

  return { client_secret: paymentIntent.client_secret as string };
}
