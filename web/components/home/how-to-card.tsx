import { Link } from '@/i18n/navigation';

import { Button } from '@/components/ui/button';
import { BookMarkedIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';

function HowToCard() {
  const t = useTranslations('home.howToCard');

  return (
    <div className="flex flex-col overflow-hidden rounded-md border border-border md:col-span-2">
      <div className="flex flex-col p-4">
        <h2 className="font-bold">
          {t.rich('title', {
            underline: (chunks) => <span className="underline">{chunks}</span>,
          })}
        </h2>
        <p className="mb-4 text-sm text-muted-foreground">
          {t.rich('description', {
            underline: (chunks) => <span className="underline">{chunks}</span>,
          })}
        </p>
        <Button asChild variant="secondary">
          <Link href="/how-to">
            <BookMarkedIcon />
            {t('button')}
          </Link>
        </Button>
      </div>
    </div>
  );
}

export default HowToCard;
