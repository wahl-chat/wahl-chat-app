import { Button } from '@/components/ui/button';
import {
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { stripe } from '@/lib/stripe/stripe';
import { CircleCheckIcon, FrownIcon } from 'lucide-react';
import Link from 'next/link';
import type Stripe from 'stripe';

async function Page({
  searchParams,
}: {
  searchParams: Promise<{ session_id: string }>;
}) {
  const actualSearchParams = await searchParams;

  if (!actualSearchParams.session_id) {
    return <PaymentFailed />;
  }

  const checkoutSession: Stripe.Checkout.Session =
    await stripe.checkout.sessions.retrieve(actualSearchParams.session_id, {
      expand: ['line_items', 'payment_intent'],
    });

  const paymentIntent = checkoutSession.payment_intent as Stripe.PaymentIntent;

  if (paymentIntent.status !== 'succeeded') {
    return <PaymentFailed />;
  }

  return (
    <>
      <CardHeader className="flex flex-col items-center justify-center">
        <CircleCheckIcon className="size-16" />
        <CardTitle className="pt-4 text-center">
          Deine Spende war erfolgreich!
        </CardTitle>
        <CardDescription className="pt-2 text-center">
          Vielen Dank für deine Unterstützung! Wir werden deine Spende
          verwenden, um die neutrale und unabhängige Informationen zu
          ermöglichen.
        </CardDescription>
      </CardHeader>
      <CardFooter>
        <Button className="w-full" asChild>
          <Link href="/">Zurück zur Startseite</Link>
        </Button>
      </CardFooter>
    </>
  );
}

function PaymentFailed() {
  return (
    <>
      <CardHeader className="flex flex-col items-center justify-center">
        <FrownIcon className="size-16" />
        <CardTitle className="pt-4 text-center">
          Deine Spende war leider nicht erfolgreich.
        </CardTitle>
        <CardDescription className="pt-2 text-center">
          Bitte versuche es erneut.
        </CardDescription>
      </CardHeader>
      <CardFooter>
        <Button className="w-full" asChild>
          <Link href="/donate">Zurück zur Spendenseite</Link>
        </Button>
      </CardFooter>
    </>
  );
}

export default Page;
