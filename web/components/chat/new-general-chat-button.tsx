'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import { useSidebar } from '@/components/ui/sidebar';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { SquarePenIcon } from 'lucide-react';
import Link from 'next/link';

/** Header shortcut for a fresh general chat; the expanded sidebar has its own. */
function NewGeneralChatButton() {
  const { isMobile, state } = useSidebar();
  const newChat = useChatStore((s) => s.newChat);

  if (!isMobile && state === 'expanded') return null;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button size="icon" variant="ghost" className="size-8" asChild>
          <Link href="/chat" onClick={() => newChat()} aria-label="Neuer Chat">
            <SquarePenIcon />
          </Link>
        </Button>
      </TooltipTrigger>
      <TooltipContent>Neuer Chat</TooltipContent>
    </Tooltip>
  );
}

export default NewGeneralChatButton;
