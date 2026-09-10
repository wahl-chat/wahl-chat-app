import DonationDialog from '@/components/donation-dialog';
import { Button } from '@/components/ui/button';
import { HeartHandshakeIcon, UsersRoundIcon } from 'lucide-react';
import Link from 'next/link';

/**
 * Cards render an h2 by default, which is right on the election home page
 * where each card is a top-level block. Under a section heading on the
 * landing page they must be h3 so the outline does not flatten.
 */
type CardTitleProps = {
  titleAs?: 'h2' | 'h3';
};

function SupportUsCard({ titleAs: Title = 'h2' }: CardTitleProps) {
  return (
    <div className="flex flex-col overflow-hidden rounded-md border border-border">
      <div className="flex flex-col p-4">
        <Title className="font-bold">Politische Bildung neu denken</Title>
        <p className="mb-4 text-sm text-muted-foreground">
          Hilf uns, laufende Kosten für die KI zu decken!
        </p>
        <div className="flex w-full flex-row gap-2 [&_button]:w-full">
          <DonationDialog>
            <Button>
              <HeartHandshakeIcon /> Spenden
            </Button>
          </DonationDialog>
          <Button variant="secondary" className="w-full" asChild>
            <Link href="/about-us">
              <UsersRoundIcon />
              Über uns
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}

export default SupportUsCard;
