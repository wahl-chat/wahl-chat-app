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
import { Link } from '@/i18n/navigation';
import { getCurrentUser } from '@/lib/firebase/firebase-server';
import { IS_EMBEDDED, getUserDetailsFromUser } from '@/lib/utils';
import {
  HeartHandshakeIcon,
  HomeIcon,
  MessageCircleIcon,
  UserIcon,
} from 'lucide-react';
import { Suspense } from 'react';
import ChatSidebarGroupSelect from './chat-sidebar-group-select';
import SidebarHistorySr from './sidebar-history-sr';
import SidebarNewChatButtons from './sidebar-new-chat-buttons';

import { LocaleSwitcher } from '@/components/locale/locale-switcher';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import { getTranslations } from 'next-intl/server';

type Props = {
  contextId?: string;
};

async function ChatSidebar({ contextId = DEFAULT_CONTEXT_ID }: Props) {
  const user = !IS_EMBEDDED ? await getCurrentUser() : undefined;

  const userDetails = user ? getUserDetailsFromUser(user) : undefined;
  const t = await getTranslations('chat.sidebar');

  return (
    <Sidebar
      mobileVisuallyHiddenTitle="wahl.chat"
      mobileVisuallyHiddenDescription={t('mobileDescription')}
    >
      <SidebarHeader className="flex h-chat-header flex-row items-center justify-between border-b border-b-muted pl-4 pr-2">
        <Link href={`/${contextId}`} className="flex items-center gap-4">
          <Logo variant="small" className="size-6" />
        </Link>
        <div className="flex flex-row items-center gap-1">
          <LocaleSwitcher
            align="start"
            className="h-8 gap-1.5 border-0 px-2 text-sm"
          />
          <ThemeModeToggle />
          <Button
            variant="ghost"
            size="icon"
            asChild
            className="size-8"
            tooltip={t('home')}
          >
            <Link href={`/${contextId}`}>
              <HomeIcon className="size-4" />
            </Link>
          </Button>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarGroupLabel>{t('newChat')}</SidebarGroupLabel>
            <SidebarNewChatButtons contextId={contextId} />

            <ChatSidebarGroupSelect contextId={contextId} />
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>{t('support')}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {!IS_EMBEDDED && (
                <SidebarMenuItem>
                  <LoginButton
                    userDetails={userDetails}
                    userDialogAsChild
                    noUserChildren={
                      <SidebarMenuButton>
                        <UserIcon className="size-4" />
                        <span>{t('login')}</span>
                      </SidebarMenuButton>
                    }
                    userChildren={
                      <SidebarMenuButton>
                        <UserIcon className="size-4" />
                        <span>{t('account')}</span>
                      </SidebarMenuButton>
                    }
                  />
                </SidebarMenuItem>
              )}
              <SidebarMenuItem>
                <DonationDialog>
                  <SidebarMenuButton>
                    <HeartHandshakeIcon className="size-4 text-red-400" />
                    <span>{t('donate')}</span>
                  </SidebarMenuButton>
                </DonationDialog>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <FeedbackDialog>
                  <SidebarMenuButton>
                    <MessageCircleIcon className="size-4 text-blue-400" />
                    <span>{t('feedback')}</span>
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
              <p>{t('loadingHistory')}</p>
            </div>
          }
        >
          <SidebarHistorySr />
        </Suspense>
        <SidebarGroup>
          <SidebarGroupLabel>{t('information')}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href="/about-us">{t('about')}</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href="/how-to">{t('howTo')}</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href={`/${contextId}/sources`}>{t('sources')}</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href="/impressum">{t('imprint')}</Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton asChild>
                  <Link href="/datenschutz">{t('privacy')}</Link>
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
