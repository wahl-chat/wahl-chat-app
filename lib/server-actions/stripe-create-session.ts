'use server';

import type { Stripe } from 'stripe';

import { headers } from 'next/headers';

import { stripe } from '@/lib/stripe/stripe';
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

  const checkoutSession: Stripe.Checkout.Session =
    await stripe.checkout.sessions.create({
      mode: 'payment',
      submit_type: 'donate',
      line_items: [
        {
          quantity: 1,
          price_data: {
            currency: CURRENCY,
            product_data: {
              name: 'wahl.chat Spende',
            },
            unit_amount: formatAmountForStripe(amount, CURRENCY),
          },
        },
      ],
      success_url: `${origin}/donate/result?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${origin}/donate`,
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
    await stripe.paymentIntents.create({
      amount: formatAmountForStripe(
        Number(data.get('customDonation') as string),
        CURRENCY,
      ),
      automatic_payment_methods: { enabled: true },
      currency: CURRENCY,
    });

  return { client_secret: paymentIntent.client_secret as string };
}
