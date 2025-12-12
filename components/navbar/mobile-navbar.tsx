'use client';

import type { UserDetails } from '@/lib/utils';
import * as Dialog from '@radix-ui/react-dialog';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import { useState } from 'react';
import MobileNavbarItems from './mobile-navbar-items';

type Props = {
  userDetails?: UserDetails;
};

function MobileNavbar({ userDetails }: Props) {
  const [isOpen, setIsOpen] = useState(false);

  const handleClose = () => {
    setIsOpen(false);
  };

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <button
          className="group absolute inset-y-0 right-0 my-auto flex size-8 flex-col items-end justify-center gap-1 rounded-md p-2 transition-colors hover:bg-muted md:hidden"
          type="button"
          aria-label="Open menu"
        >
          <div className="h-[2px] w-4 rounded-full bg-foreground transition-all duration-300 group-data-[state=open]:translate-y-[3px] group-data-[state=open]:rotate-45" />
          <div className="h-[2px] w-5 rounded-full bg-foreground transition-all duration-300 group-data-[state=open]:w-4 group-data-[state=open]:-translate-y-[3px] group-data-[state=open]:-rotate-45" />
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 top-[var(--header-height)] z-50 bg-background/80 md:hidden" />

        <Dialog.Content className="fixed inset-x-0 bottom-0 top-[calc(var(--header-height)-1px)] z-50 flex flex-col items-center justify-center bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 md:hidden">
          <VisuallyHidden>
            <Dialog.Title>Dialog Title</Dialog.Title>
            <Dialog.Description>Dialog Description</Dialog.Description>
          </VisuallyHidden>

          <MobileNavbarItems
            userDetails={userDetails}
            mobileClose={handleClose}
          />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default MobileNavbar;
