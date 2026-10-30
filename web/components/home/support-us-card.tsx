import DonationDialog from '@/components/donation-dialog';
import { Button } from '@/components/ui/button';
import { Link } from '@/i18n/navigation';
import { HeartHandshakeIcon, UsersRoundIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';

/**
 * Cards render an h2 by default, which is right on the election home page
 * where each card is a top-level block. Under a section heading on the
 * landing page they must be h3 so the outline does not flatten.
 */
type CardTitleProps = {
  titleAs?: 'h2' | 'h3';
};

function SupportUsCard({ titleAs: Title = 'h2' }: CardTitleProps) {
  const t = useTranslations('home.supportUsCard');

  return (
    <div className="flex flex-col overflow-hidden rounded-md border border-border">
      <div className="flex flex-col p-4">
        <Title className="font-bold">{t('title')}</Title>
        <p className="mb-4 text-sm text-muted-foreground">{t('description')}</p>
        <div className="flex w-full flex-row gap-2 [&_button]:w-full">
          <DonationDialog>
            <Button>
              <HeartHandshakeIcon /> {t('donate')}
            </Button>
          </DonationDialog>
          <Button variant="secondary" className="w-full" asChild>
            <Link href="/about-us">
              <UsersRoundIcon />
              {t('aboutUs')}
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

export default SupportUsCard;
