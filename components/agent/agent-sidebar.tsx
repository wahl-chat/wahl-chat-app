'use client';

import Link from 'next/link';
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
import { HomeIcon } from 'lucide-react';
import { ThemeModeToggle } from '@/components/chat/theme-mode-toggle';

export default function AgentSidebar() {
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
        <SidebarGroup>
          <SidebarGroupLabel>Wahl Agent</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href="/agent">Neues Gespräch</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

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

