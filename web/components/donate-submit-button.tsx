'use client';

import { useFormStatus } from 'react-dom';
import { Button } from './ui/button';

type Props = {
  amount: number;
};

export function DonateSubmitButton({ amount }: Props) {
  const { pending } = useFormStatus();

  return (
    <Button className="w-full" disabled={pending || amount < 5} type="submit">
      Jetzt spenden
    </Button>
  );
}
