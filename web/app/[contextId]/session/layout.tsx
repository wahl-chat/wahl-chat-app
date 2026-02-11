import AnonymousUserChatStoreUpdater from '@/components/auth/anonymous-user-chat-store-updater';
import ChatHeader from '@/components/chat/chat-header';
import ChatSidebar from '@/components/chat/sidebar/chat-sidebar';
import { ChatStoreProvider } from '@/components/providers/chat-store-provider';
import SocketProvider from '@/components/providers/socket-provider';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';

type Props = {
  children: React.ReactNode;
  params: Promise<{
    contextId: string;
  }>;
};

async function SessionLayout({ children, params }: Props) {
  const { contextId } = await params;

  return (
    <ChatStoreProvider contextId={contextId}>
      <AnonymousUserChatStoreUpdater />
      <SocketProvider>
        <SidebarProvider defaultOpen={true}>
          <ChatSidebar contextId={contextId} />
          <SidebarInset className="flex h-dvh flex-col overflow-hidden">
            <ChatHeader contextId={contextId} />
            {children}
          </SidebarInset>
        </SidebarProvider>
      </SocketProvider>
    </ChatStoreProvider>
  );
}

export default SessionLayout;
