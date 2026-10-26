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
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';

function WahlSwiperProlificDisclaimer() {
  const t = useTranslations('swiper.prolificDisclaimer');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(true);
  }, []);

  return (
    <ResponsiveDialog open={open} onOpenChange={setOpen}>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{t('title')}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {t('description')}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <p className="px-4 text-sm md:px-0">
          <span className="my-2 block rounded-md border border-border bg-muted p-4">
            {t.rich('requirement', {
              b: (chunks) => <span className="font-semibold">{chunks}</span>,
            })}
          </span>
          {t('keepTabOpen')}
          <span className="mt-2 block font-semibold">{t('codeAtEnd')}</span>
        </p>
        <ResponsiveDialogFooter>
          <ResponsiveDialogClose asChild>
            <Button className="w-full">{t('start')}</Button>
          </ResponsiveDialogClose>
        </ResponsiveDialogFooter>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default WahlSwiperProlificDisclaimer;
