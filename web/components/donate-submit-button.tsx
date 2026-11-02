'use client';

import { useTranslations } from 'next-intl';
import { useFormStatus } from 'react-dom';
import { Button } from './ui/button';

type Props = {
  amount: number;
};

export function DonateSubmitButton({ amount }: Props) {
  const t = useTranslations('donate.form');
  const { pending } = useFormStatus();

  return (
    <Button className="w-full" disabled={pending || amount < 5} type="submit">
      {t('submit')}
    </Button>
  );
}
