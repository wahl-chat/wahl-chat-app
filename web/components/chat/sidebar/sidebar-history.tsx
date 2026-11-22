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
import { sessionContextId, sessionHref } from '@/lib/chat-history';
import type { ChatSession, Context } from '@/lib/firebase/firebase.types';
import { useChatHistory } from '@/lib/hooks/use-chat-history';
import { cn } from '@/lib/utils';
import { MessageSquareIcon, VoteIcon } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';

type Props = {
  history?: ChatSession[];
};

function ContextIconSmall({
  contextId,
  context,
}: {
  contextId: string;
  context?: Context;
}) {
  const [imageError, setImageError] = useState(false);

  // Use icon_url if available, otherwise fallback to local image
  const iconUrl = context?.icon_url || `/images/${contextId}.webp`;

  // Reset image error when context or icon URL changes
  useEffect(() => {
    setImageError(false);
  }, [contextId, iconUrl]);

  if (imageError) {
    return <VoteIcon className="size-4 shrink-0 text-muted-foreground" />;
  }

  return (
    <Image
      src={iconUrl}
      alt={context?.name ?? contextId}
      className="size-4 shrink-0 rounded object-contain"
      width={16}
      height={16}
      onError={() => setImageError(true)}
    />
  );
}

function SidebarHistory({ history: initialHistory }: Props) {
  const history = useChatHistory(initialHistory);
  // Election contexts only, so a general session finds none and stays untagged.
  const contexts = useContexts();
  const chatSessionId = useChatStore((state) => state.chatSessionId);
  const { setOpenMobile } = useSidebar();

  function handleClick() {
    setOpenMobile(false);
  }

  if (history.length === 0) return null;

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Historie</SidebarGroupLabel>

      <SidebarGroupContent>
        <SidebarMenu>
          {history.map((item) => {
            const contextId = sessionContextId(item);
            const election = contexts.find((c) => c.context_id === contextId);

            return (
              <SidebarMenuItem key={item.id}>
                <SidebarMenuButton
                  asChild
                  className={cn(chatSessionId === item.id && 'bg-muted')}
                >
                  <Link href={sessionHref(item)} onClick={handleClick}>
                    {election ? (
                      <ContextIconSmall
                        contextId={contextId}
                        context={election}
                      />
                    ) : (
                      <MessageSquareIcon className="size-4 shrink-0 text-muted-foreground" />
                    )}
                    <span className="w-full truncate">
                      {item.title ||
                        item.party_ids?.join(',') ||
                        item.party_id ||
                        'wahl.chat'}
                    </span>
                    {election && (
                      <span className="max-w-20 shrink-0 truncate rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium leading-none text-muted-foreground">
                        {election.location_name || election.name}
                      </span>
                    )}
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}

export default SidebarHistory;
