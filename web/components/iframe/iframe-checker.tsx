'use client';

import { useTenant } from '@/components/providers/tenant-provider';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import Link from 'next/link';
import { useEffect, useState } from 'react';

function IframeChecker() {
  const tenant = useTenant();
  const [showAlert, setShowAlert] = useState<boolean>(false);

  useEffect(() => {
    const isInIframe = window.self !== window.top;

    if (isInIframe && !tenant) {
      setShowAlert(true);
    }
  }, [tenant]);

  if (!showAlert) {
    return null;
  }

  return (
    <AlertDialog open={showAlert} onOpenChange={setShowAlert}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Berechtigung zur Einbindung benötigt
          </AlertDialogTitle>
          <AlertDialogDescription>
            Um wahl.chat in einem iFrame zu verwenden, nimm bitte Kontakt zu uns
            über die E-Mail-Adresse{' '}
            <Link className="underline" href="mailto:info@wahl.chat">
              info@wahl.chat
            </Link>{' '}
            auf.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter>
          <AlertDialogCancel>Schließen</AlertDialogCancel>
          <Button>
            <Link href="mailto:info@wahl.chat">Kontaktiere uns</Link>
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default IframeChecker;
