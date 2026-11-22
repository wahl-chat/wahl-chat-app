'use client';

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { NewspaperIcon, PlusIcon, UsersIcon } from 'lucide-react';
import { useState } from 'react';
import ChatFeedPicker from './chat-feed-picker';
import ChatFocusDialog from './chat-focus-dialog';

type Props = {
  disabled: boolean;
};

/** The general chat's "+": a party focus or a feed item as the topic. */
function ChatInputGeneralMenu({ disabled }: Props) {
  const [dialog, setDialog] = useState<'parties' | 'feed' | null>(null);
  const close = (open: boolean) => {
    if (!open) setDialog(null);
  };

  return (
    <>
      {/* Not modal: a modal menu's focus trap would fight the dialog it opens. */}
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <button
            className="flex shrink-0 items-center gap-1 rounded-full bg-primary p-1 text-primary-foreground transition-all duration-200 ease-out enabled:hover:scale-95 disabled:cursor-not-allowed"
            disabled={disabled}
            type="button"
            aria-label="Parteien oder Thema aus dem Feed wählen"
          >
            <PlusIcon className="size-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" side="top">
          <DropdownMenuItem onSelect={() => setDialog('parties')}>
            <UsersIcon />
            Parteien
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setDialog('feed')}>
            <NewspaperIcon />
            Aus dem Feed
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <ChatFocusDialog open={dialog === 'parties'} onOpenChange={close} />
      <ChatFeedPicker open={dialog === 'feed'} onOpenChange={close} />
    </>
  );
}

export default ChatInputGeneralMenu;
