'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
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
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { listenToHistory } from '@/lib/firebase/firebase';
import type { ChatSession } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { VoteIcon } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useEffect, useState } from 'react';

type Props = {
  history?: ChatSession[];
};

function ContextIconSmall({ contextId }: { contextId: string }) {
  const contexts = useContexts();
  const context = contexts.find((c) => c.context_id === contextId);
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
  const { user } = useAnonymousAuth();
  const [history, setHistory] = useState<ChatSession[]>(initialHistory ?? []);
  const chatSessionId = useChatStore((state) => state.chatSessionId);
  const { setOpenMobile } = useSidebar();

  useEffect(() => {
    if (!user?.uid) return;

    const unsubscribe = listenToHistory(user.uid, (history) => {
      setHistory(history);
    });

    return () => unsubscribe();
  }, [user?.uid]);

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
            // Use session's context_id if available, otherwise fall back to the default context
            const sessionContextId = item.context_id ?? DEFAULT_CONTEXT_ID;

            return (
              <SidebarMenuItem key={item.id}>
                <SidebarMenuButton
                  asChild
                  className={cn(chatSessionId === item.id && 'bg-muted')}
                >
                  <Link
                    href={`/${sessionContextId}/session/${item.id}`}
                    onClick={handleClick}
                  >
                    <ContextIconSmall contextId={sessionContextId} />
                    <span className="w-full truncate">
                      {item.title ||
                        item.party_ids?.join(',') ||
                        item.party_id ||
                        'wahl.chat'}
                    </span>
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
