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
import WahlSwiperShareLinkInputForm from './wahl-swiper-share-input-form';

function WahlSwiperShareButton() {
  return (
    <ResponsiveDialog>
      <ResponsiveDialogTrigger asChild>
        <Button variant="secondary">
          <ShareIcon />
          Teilen
        </Button>
      </ResponsiveDialogTrigger>

      <ResponsiveDialogContent className="sm:max-w-md">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>Swiper Ergebnis teilen</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Jeder, der diesen Link hat, kann dieses Ergebnis sehen.
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
