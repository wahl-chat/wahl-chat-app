'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ShareIcon } from 'lucide-react';
import ChatShareLinkInputForm from './chat-share-link-input-form';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './responsive-drawer-dialog';

function ChatShareButton() {
  const sharePrivateSession = useChatStore(
    (state) => state.messages.length > 0,
  );

  return (
    <ResponsiveDialog>
      <Tooltip>
        <TooltipTrigger asChild>
          <ResponsiveDialogTrigger asChild>
            <Button variant="ghost" size="icon" className="size-8">
              <ShareIcon />
            </Button>
          </ResponsiveDialogTrigger>
        </TooltipTrigger>
        <TooltipContent>Chat Session teilen</TooltipContent>
      </Tooltip>
      <ResponsiveDialogContent className="sm:max-w-md">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle>
            {sharePrivateSession ? 'Chat Session teilen' : 'wahl.chat teilen'}
          </ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {sharePrivateSession
              ? 'Jeder, der diesen Link hat, kann diese Chat Session sehen.'
              : 'Teile wahl.chat mit Freunden und Familie.'}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>

        <div className="p-4 md:p-0">
          <ChatShareLinkInputForm sharePrivateSession={sharePrivateSession} />
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default ChatShareButton;
