import LoginButton from '@/components/auth/login-button';
import Logo from '@/components/chat/logo';
import { ThemeModeToggle } from '@/components/chat/theme-mode-toggle';
import DonationDialog from '@/components/donation-dialog';
import FeedbackDialog from '@/components/feedback-dialog';
import LoadingSpinner from '@/components/loading-spinner';
import { Button } from '@/components/ui/button';
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
import { getCurrentUser } from '@/lib/firebase/firebase-server';
import { getUserDetailsFromUser } from '@/lib/utils';
import {
  HeartHandshakeIcon,
  HomeIcon,
  MessageCircleIcon,
  UserIcon,
} from 'lucide-react';
import Link from 'next/link';
import { Suspense } from 'react';
import ChatSidebarGroupSelect from './chat-sidebar-group-select';
import SidebarHistorySr from './sidebar-history-sr';
import SidebarNewChatButtons from './sidebar-new-chat-buttons';
import SidebarSwiperTeaser from './sidebar-swiper-teaser';

async function ChatSidebar() {
  const user = await getCurrentUser();

  const userDetails = user ? getUserDetailsFromUser(user) : undefined;

  return (
    <Sidebar
      mobileVisuallyHiddenTitle="wahl.chat"
      mobileVisuallyHiddenDescription="Starte einen neuen Chat oder wähle eine vorherige Konversation aus."
    >
      <SidebarHeader className="flex h-chat-header flex-row items-center justify-between border-b border-b-muted pl-4 pr-2">
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
          <SidebarGroupContent>
            <SidebarSwiperTeaser />
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarGroupLabel>Neuer Chat</SidebarGroupLabel>
            <SidebarNewChatButtons />

            <ChatSidebarGroupSelect />
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>Unterstütze wahl.chat</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <LoginButton
                  userDetails={userDetails}
                  userDialogAsChild
                  noUserChildren={
                    <SidebarMenuButton>
                      <UserIcon className="size-4" />
                      <span>Anmelden</span>
                    </SidebarMenuButton>
                  }
                  userChildren={
                    <SidebarMenuButton>
                      <UserIcon className="size-4" />
                      <span>Account</span>
                    </SidebarMenuButton>
                  }
                />
              </SidebarMenuItem>
              <SidebarMenuItem>
                <DonationDialog>
                  <SidebarMenuButton>
                    <HeartHandshakeIcon className="size-4 text-red-400" />
                    <span>Spenden</span>
                  </SidebarMenuButton>
                </DonationDialog>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <FeedbackDialog>
                  <SidebarMenuButton>
                    <MessageCircleIcon className="size-4 text-blue-400" />
                    <span>Feedback</span>
                  </SidebarMenuButton>
                </FeedbackDialog>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <Suspense
          fallback={
            <div className="flex h-32 flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
              <LoadingSpinner />
              <p>Lade Historie...</p>
            </div>
          }
        >
          <SidebarHistorySr />
        </Suspense>
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
                  <Link href="/how-to">Wie funktioniert wahl.chat?</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href="/sources">Quellen</Link>
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

export default ChatSidebar;
