'use client';

import { formatAmountForDisplay } from '@/lib/stripe/stripe-helpers';
import {
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from './ui/card';
import { createCheckoutSession } from '@/lib/server-actions/stripe-create-session';
import { useState } from 'react';
import { Button } from './ui/button';
import { Slider } from './ui/slider';
import { DonateSubmitButton } from './donate-submit-button';
import { cn } from '@/lib/utils';
import { Input } from './ui/input';
import Link from 'next/link';
import NumberFlow from '@number-flow/react';
import { EqualIcon } from 'lucide-react';
import { track } from '@vercel/analytics/react';

function DonationForm() {
  const [amount, setAmount] = useState(50);
  const [customAmount, setCustomAmount] = useState(false);

  const defaultAmounts = [5, 10, 20, 50, 100, 200, 500];

  const handleDonate = async (data: FormData) => {
    track('donation_started', {
      amount: amount,
    });

    const result = await createCheckoutSession(data);

    if (result.url) {
      window.location.assign(result.url);
    }
  };

  const handleSetAmount = (amount: number) => {
    setAmount(amount);
    setCustomAmount(false);
  };

  const handleSliderChange = (value: number[]) => {
    setAmount(value[0]);
    if (customAmount) setCustomAmount(false);
  };

  return (
    <form action={handleDonate}>
      <CardHeader>
        <CardTitle className="text-center text-2xl">
          Halte{' '}
          <Link className="underline" href="/">
            wahl.chat
          </Link>{' '}
          mit deiner Spende am Leben!
        </CardTitle>
        <CardDescription className="text-center">
          Wir finanzieren{' '}
          <Link className="underline" href="/">
            wahl.chat
          </Link>{' '}
          derzeit noch vollständig aus eigener Tasche. Deine Spende hilft uns,
          dieses Projekt weiter zu betreiben und die Kosten für Server und KI zu
          decken.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-[1fr,auto,1fr] items-center gap-4">
          <div className="mb-8 mt-4 flex flex-col items-center justify-center">
            {customAmount ? (
              <Input
                type="number"
                name="amount"
                min="5"
                max="10000"
                step="1"
                className="mb-2 h-16 w-32 text-center !text-4xl font-bold [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                value={amount}
                onChange={(e) => {
                  const value = Math.max(0, Math.floor(Number(e.target.value)))
                    .toString()
                    .replace(/^0+/, '');
                  setAmount(Number(value));
                }}
              />
            ) : (
              <h1 className="text-center text-4xl font-bold">
                <NumberFlow value={amount} />{' '}
                <span className="text-lg text-muted-foreground">€</span>
              </h1>
            )}
            <p className="text-center text-sm text-muted-foreground">
              einmalige Spende
            </p>
          </div>
          <EqualIcon className="text-3xl" />
          <div className="mb-8 mt-4 flex flex-col items-center justify-center">
            <h1 className="text-center text-4xl font-bold">
              <NumberFlow value={amount * 50} />
            </h1>
            <p className="text-center text-sm text-muted-foreground">
              Menschen informiert
            </p>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2">
          {defaultAmounts.map((currAmount) => (
            <Button
              key={currAmount}
              variant="outline"
              type="button"
              className={cn(
                amount === currAmount &&
                  'bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground/90',
              )}
              onClick={() => handleSetAmount(currAmount)}
            >
              {formatAmountForDisplay(currAmount)} €
            </Button>
          ))}
          <Button
            type="button"
            variant="outline"
            className={cn(
              customAmount &&
                'bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground/90',
            )}
            onClick={() => setCustomAmount(true)}
          >
            Andere
          </Button>
        </div>

        <Slider
          className="my-8"
          defaultValue={[50]}
          min={10}
          max={5000}
          step={10}
          value={[amount]}
          onValueChange={handleSliderChange}
        />

        <input type="hidden" name="amount" value={amount} />
      </CardContent>
      <CardFooter>
        <DonateSubmitButton amount={amount} />
      </CardFooter>
    </form>
  );
}

export default DonationForm;
