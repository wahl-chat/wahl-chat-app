'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogClose,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { Button } from '@/components/ui/button';
import { useEffect, useState } from 'react';

function WahlSwiperProlificDisclaimer() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(true);
  }, []);

  return (
    <ResponsiveDialog open={open} onOpenChange={setOpen}>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>Willkommen zur Studie</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Wichtige Informationen
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <div className="px-4 text-sm md:px-0">
          <p className="mb-4">
            Vielen Dank, dass du an unserer Studie teilnimmst!
          </p>
          <div className="rounded-md border border-amber-500 bg-amber-50 p-4 dark:bg-amber-950">
            <p className="font-semibold text-amber-800 dark:text-amber-200">
              Bitte schliesse diesen Browser-Tab nicht, bevor du den
              Abschlusscode erhalten hast.
            </p>
            <p className="mt-2 text-amber-700 dark:text-amber-300">
              Der Code wird dir am Ende des Swipers angezeigt und ist notwendig,
              um die Studie abzuschliessen.
            </p>
          </div>
        </div>

        <ResponsiveDialogFooter>
          <ResponsiveDialogClose asChild>
            <Button className="w-full">Verstanden, los geht&apos;s!</Button>
          </ResponsiveDialogClose>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default WahlSwiperProlificDisclaimer;
