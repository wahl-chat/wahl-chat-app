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
import { Link } from '@/i18n/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

function IframeChecker() {
  const t = useTranslations('chat.iframe');
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
          <AlertDialogTitle>{t('title')}</AlertDialogTitle>
          <AlertDialogDescription>
            {t.rich('description', {
              email: (chunks) => (
                <Link className="underline" href="mailto:info@wahl.chat">
                  {chunks}
                </Link>
              ),
            })}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter>
          <AlertDialogCancel>{t('close')}</AlertDialogCancel>
          <Button>
            <Link href="mailto:info@wahl.chat">{t('contact')}</Link>
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default IframeChecker;
