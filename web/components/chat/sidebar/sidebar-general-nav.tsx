'use client';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { useContexts } from '@/components/providers/context-provider';
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar';
import { generalChatHref } from '@/lib/chat-history';
import { liveElections } from '@/lib/elections';
import { useChatHistory } from '@/lib/hooks/use-chat-history';
import { formatGermanDate } from '@/lib/utils';
import {
  ArrowRightIcon,
  MessageSquareIcon,
  SquarePenIcon,
  VoteIcon,
} from 'lucide-react';
import Link from 'next/link';

/** Starts a fresh general chat. */
export function SidebarNewGeneralChatButton() {
  const newChat = useChatStore((state) => state.newChat);
  const { setOpenMobile } = useSidebar();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton asChild>
          <Link
            href="/chat"
            onClick={() => {
              // /chat after /chat?session_id=… re-renders with identical props,
              // so the store would keep the old conversation.
              newChat();
              setOpenMobile(false);
            }}
          >
            <SquarePenIcon className="size-4" />
            <span>Neuer Chat</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}

/** Live elections plus the way to every other one. */
export function SidebarElections() {
  const elections = liveElections(useContexts());
  const { setOpenMobile } = useSidebar();

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Wahlen</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {elections.map((election) => (
            <SidebarMenuItem key={election.context_id}>
              <SidebarMenuButton asChild className="h-auto py-1.5">
                <Link
                  href={`/${election.context_id}/session`}
                  onClick={() => setOpenMobile(false)}
                >
                  <VoteIcon className="size-4" />
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate">{election.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {formatGermanDate(election.date)}
                    </span>
                  </span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
          <SidebarMenuItem>
            <SidebarMenuButton asChild>
              <Link href="/election-chat" onClick={() => setOpenMobile(false)}>
                <ArrowRightIcon className="size-4" />
                <span>Alle Wahlen</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}

/** Way back from an election chat to the user's general chat. */
export function SidebarGeneralChatLink() {
  const href = generalChatHref(useChatHistory());
  const { setOpenMobile } = useSidebar();

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton asChild>
          <Link href={href} onClick={() => setOpenMobile(false)}>
            <MessageSquareIcon className="size-4" />
            <span>Allgemeiner Chat</span>
          </Link>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
