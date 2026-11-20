'use client';

import { Button } from '@/components/ui/button';
import { generalChatHref } from '@/lib/chat-history';
import { useChatHistory } from '@/lib/hooks/use-chat-history';
import { ArrowLeftIcon } from 'lucide-react';
import Link from 'next/link';

/** From an election chat back to the user's latest general chat. */
function ChatGeneralBackLink() {
  const href = generalChatHref(useChatHistory());

  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-8 shrink-0 gap-1.5 px-2"
      asChild
    >
      <Link href={href} aria-label="Allgemeiner Chat">
        <ArrowLeftIcon aria-hidden />
        {/* Short on phones, where it shares a row with the election switcher. */}
        <span aria-hidden className="sm:hidden">
          Allgemein
        </span>
        <span aria-hidden className="hidden sm:inline">
          Allgemeiner Chat
        </span>
      </Link>
    </Button>
  );
}

export default ChatGeneralBackLink;
