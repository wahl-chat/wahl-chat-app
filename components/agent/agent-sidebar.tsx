'use client';

import Link from 'next/link';
import { useState } from 'react';
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar';
import Logo from '@/components/chat/logo';
import { Button } from '@/components/ui/button';
import { HomeIcon, CopyIcon, CheckIcon, Info } from 'lucide-react';
import { ThemeModeToggle } from '@/components/chat/theme-mode-toggle';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export default function AgentSidebar() {
  const conversationId = useAgentStore((state) => state.conversationId);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!conversationId) return;
    await navigator.clipboard.writeText(conversationId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Sidebar
      mobileVisuallyHiddenTitle="Wahl Agent"
      mobileVisuallyHiddenDescription="Einstellungen und Informationen zum Wahl Agent."
    >
      <SidebarHeader className="flex h-[65px] flex-row items-center justify-between border-b border-b-muted pl-4 pr-2">
        <Link href="/" className="flex items-center gap-4">
          <Logo variant="small" className="size-6" />
        </Link>
        <div className="flex flex-row items-center gap-1">
          <ThemeModeToggle />
          <Button
            variant="ghost"
            size="icon"
            asChild
            className="size-8"
            tooltip="Startseite"
          >
            <Link href="/">
              <HomeIcon className="size-4" />
            </Link>
          </Button>
        </div>
      </SidebarHeader>
      <SidebarContent>
        {conversationId && (
          <SidebarGroup>
              <SidebarGroupLabel className="flex items-center gap-1.5">
                <span>Conversation ID</span>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Info className="size-3 text-muted-foreground cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[200px] text-xs">
                    Speichere diese ID, um die Konversation auf einem anderen Gerät oder zu einem späteren Zeitpunkt fortzusetzen.
                  </TooltipContent>
                </Tooltip>
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <div className="flex w-full items-center gap-2 px-2 py-1.5">
                      <span className="flex-1 truncate font-mono text-xs text-muted-foreground">
                        {conversationId}
                      </span>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-6 shrink-0"
                        onClick={handleCopy}
                        tooltip={copied ? 'Kopiert!' : 'ID kopieren'}
                      >
                        {copied ? (
                          <CheckIcon className="size-3.5" />
                        ) : (
                          <CopyIcon className="size-3.5" />
                        )}
                      </Button>
                    </div>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
        )}

        <SidebarGroup>
          <SidebarGroupLabel>Informationen</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href="/about-us">Über wahl.chat</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href="/impressum">Impressum</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href="/datenschutz">Datenschutz</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  );
}
