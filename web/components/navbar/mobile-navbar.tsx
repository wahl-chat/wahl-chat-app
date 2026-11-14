'use client';

import FeedbackDialog from '@/components/feedback-dialog';
import { type UserDetails, cn } from '@/lib/utils';
import * as Dialog from '@radix-ui/react-dialog';
import { VisuallyHidden } from '@radix-ui/react-visually-hidden';
import { useState } from 'react';
import MobileNavbarItems from './mobile-navbar-items';

type Props = {
  userDetails?: UserDetails;
  /** Shows the menu at every width, for pages without a desktop navbar. */
  alwaysVisible?: boolean;
};

function MobileNavbar({ userDetails, alwaysVisible = false }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);

  const handleClose = () => {
    setIsOpen(false);
  };

  const handleFeedback = () => {
    setIsOpen(false);
    setIsFeedbackOpen(true);
  };

  const hiddenOnDesktop = !alwaysVisible && 'md:hidden';

  return (
    <>
      <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
        <Dialog.Trigger asChild>
          <button
            className={cn(
              'group flex size-8 shrink-0 flex-col items-end justify-center gap-1 rounded-md p-2 transition-colors hover:bg-muted',
              hiddenOnDesktop,
            )}
            type="button"
            aria-label="Open menu"
          >
            <div className="h-[2px] w-4 rounded-full bg-foreground transition-all duration-300 group-data-[state=open]:translate-y-[3px] group-data-[state=open]:rotate-45" />
            <div className="h-[2px] w-5 rounded-full bg-foreground transition-all duration-300 group-data-[state=open]:w-4 group-data-[state=open]:-translate-y-[3px] group-data-[state=open]:-rotate-45" />
          </button>
        </Dialog.Trigger>

        <Dialog.Portal>
          <Dialog.Overlay
            className={cn(
              'fixed inset-0 top-[var(--header-height)] z-50 bg-background/80',
              hiddenOnDesktop,
            )}
          />

          <Dialog.Content
            className={cn(
              'fixed inset-x-0 bottom-0 top-[calc(var(--header-height)-1px)] z-50 flex flex-col items-center justify-center bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
              hiddenOnDesktop,
            )}
          >
            <VisuallyHidden>
              <Dialog.Title>Dialog Title</Dialog.Title>
              <Dialog.Description>Dialog Description</Dialog.Description>
            </VisuallyHidden>

            <MobileNavbarItems
              userDetails={userDetails}
              mobileClose={handleClose}
              onFeedback={handleFeedback}
            />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Outside the menu, whose content unmounts when it closes. */}
      <FeedbackDialog open={isFeedbackOpen} onOpenChange={setIsFeedbackOpen} />
    </>
  );
}

export default MobileNavbar;
