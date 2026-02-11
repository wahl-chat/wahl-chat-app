import DonationDialog from '@/components/donation-dialog';
import { Button } from '@/components/ui/button';
import { BadgeEuroIcon, HeartHandshakeIcon } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Budget aufgebraucht',
  description:
    'Das Budget von wahl.chat ist derzeit aufgebraucht. Unterstütze uns mit einer Spende.',
  robots: 'noindex',
};

function BudgetSpent() {
  return (
    <section className="mx-auto flex h-full max-w-lg flex-col items-center justify-center space-y-4 p-4 text-center">
      <BadgeEuroIcon className="size-12" />
      <h1 className="text-2xl font-bold">Budget aufgebraucht</h1>
      <p>
        Da wir uns ausschließlich mit Spenden finanzieren, kann es dazu kommen,
        dass unser budget aufgebraucht ist.
      </p>
      <p>Wenn du uns unterstützen möchtest, kannst du uns gerne spenden.</p>
      <div className="flex justify-center gap-2">
        <DonationDialog>
          <Button>
            <HeartHandshakeIcon />
            Unterstütze uns
          </Button>
        </DonationDialog>
        <Button variant="outline" asChild>
          <Link href="/about-us">Über uns</Link>
        </Button>
      </div>
    </section>
  );
}

export default BudgetSpent;
