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

function WahlSwiperExperimentalDisclaimer() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(true);
  }, []);

  return (
    <ResponsiveDialog open={open} onOpenChange={setOpen}>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>⚠️ Disclaimer</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Experimentelles Feature
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <p className="px-4 text-sm md:px-0">
          Ihr habt euch eine Art Wahl-O-Mat gewünscht – hier ist ein erster
          Versuch, euer Feedback umzusetzen.
          <span className="my-2 block rounded-md border border-border bg-muted p-4 font-semibold">
            Wir möchten ausdrücklich betonen, dass dies lediglich ein erster
            Entwurf ist und keine offizielle Wahlempfehlung darstellt.
          </span>
          Dein Feedback hilft uns, zur nächsten Wahl eine finale Version zu
          entwickeln, die bestehende Probleme löst.
          <span className="mt-2 block font-semibold">
            Vielen Dank für euer Verständnis 🙏 - wir freuen uns auf eure
            Rückmeldungen! 🤗
          </span>
        </p>

        <ResponsiveDialogFooter>
          <ResponsiveDialogClose asChild>
            <Button className="w-full">Los geht&apos;s!</Button>
          </ResponsiveDialogClose>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default WahlSwiperExperimentalDisclaimer;
