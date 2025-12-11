import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { BookMarkedIcon } from 'lucide-react';

function HowToCard() {
  return (
    <div className="flex flex-col overflow-hidden rounded-md border border-border md:order-last md:col-span-2">
      <div className="flex flex-col p-4">
        <h2 className="font-bold">
          Wie funktioniert <span className="underline">wahl.chat</span>?
        </h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Lerne, was du mit <span className="underline">wahl.chat</span> alles
          machen kannst und welche Funktionen du nutzen kannst.
        </p>
        <Button asChild variant="secondary">
          <Link href="/how-to">
            <BookMarkedIcon />
            Anleitung
          </Link>
        </Button>
      </div>
    </div>
  );
}

export default HowToCard;
