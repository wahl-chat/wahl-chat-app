'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from '@/components/chat/responsive-drawer-dialog';
import { Button } from '@/components/ui/button';
import {} from '@/components/ui/tooltip';
import { ShareIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';
import WahlSwiperShareLinkInputForm from './wahl-swiper-share-input-form';

function WahlSwiperShareButton() {
  const t = useTranslations('swiper.share');

  return (
    <ResponsiveDialog>
      <ResponsiveDialogTrigger asChild>
        <Button variant="secondary">
          <ShareIcon />
          {t('button')}
        </Button>
      </ResponsiveDialogTrigger>

      <ResponsiveDialogContent className="sm:max-w-md">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>{t('title')}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {t('description')}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        <div className="p-4 md:p-0">
          <WahlSwiperShareLinkInputForm />
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default WahlSwiperShareButton;
