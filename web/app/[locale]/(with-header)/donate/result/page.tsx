import { Button } from '@/components/ui/button';
import {
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Link } from '@/i18n/navigation';
import { getStripe } from '@/lib/stripe/stripe';
import { CircleCheckIcon, FrownIcon } from 'lucide-react';
import { getTranslations } from 'next-intl/server';
import type Stripe from 'stripe';

async function Page({
  searchParams,
}: {
  searchParams: Promise<{ session_id: string }>;
}) {
  const actualSearchParams = await searchParams;
  const t = await getTranslations('donate.result');

  if (!actualSearchParams.session_id) {
    return <PaymentFailed />;
  }

  const checkoutSession: Stripe.Checkout.Session =
    await getStripe().checkout.sessions.retrieve(
      actualSearchParams.session_id,
      {
        expand: ['line_items', 'payment_intent'],
      },
    );

  const paymentIntent = checkoutSession.payment_intent as Stripe.PaymentIntent;

  if (paymentIntent.status !== 'succeeded') {
    return <PaymentFailed />;
  }

  return (
    <>
      <CardHeader className="flex flex-col items-center justify-center">
        <CircleCheckIcon className="size-16" />
        <CardTitle className="pt-4 text-center">{t('successTitle')}</CardTitle>
        <CardDescription className="pt-2 text-center">
          {t('successDescription')}
        </CardDescription>
      </CardHeader>
      <CardFooter>
        <Button className="w-full" asChild>
          <Link href="/">{t('backHome')}</Link>
        </Button>
      </CardFooter>
    </>
  );
}

async function PaymentFailed() {
  const t = await getTranslations('donate.result');

  return (
    <>
      <CardHeader className="flex flex-col items-center justify-center">
        <FrownIcon className="size-16" />
        <CardTitle className="pt-4 text-center">{t('failedTitle')}</CardTitle>
        <CardDescription className="pt-2 text-center">
          {t('failedDescription')}
        </CardDescription>
      </CardHeader>
      <CardFooter>
        <Button className="w-full" asChild>
          <Link href="/donate">{t('backToDonate')}</Link>
        </Button>
      </CardFooter>
    </>
  );
}

export default Page;
