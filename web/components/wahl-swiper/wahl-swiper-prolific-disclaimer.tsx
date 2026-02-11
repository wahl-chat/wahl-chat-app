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
                <p className="px-4 text-sm md:px-0">
          <span className="my-2 block rounded-md border border-border bg-muted p-4">
            Um den Abschlusscode zu erhalten, musst du mindestens
            <span className="font-semibold"> eine </span>
            Frage mit
            <span className="font-semibold"> ja </span>
            oder
            <span className="font-semibold"> nein </span>
            beantworten.
          </span>
                    Bitte schliesse diesen Browser-Tab nicht, bevor du den Abschlusscode erhalten hast.
                    <span className="mt-2 block font-semibold">

            Der Code wird dir am Ende des Swipers angezeigt und ist notwendig, um die Studie abzuschliessen.
          </span>
                </p>
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