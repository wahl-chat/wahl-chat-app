import ChatHeader from '@/components/chat/chat-header';
import ChatSidebar from '@/components/chat/sidebar/chat-sidebar';
import { ChatStoreProvider } from '@/components/providers/chat-store-provider';
import SkipLink from '@/components/skip-link';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';

type Props = {
  children: React.ReactNode;
  params: Promise<{
    contextId: string;
  }>;
};

async function ExploreLayout({ children, params }: Props) {
  const { contextId } = await params;

  return (
    <ChatStoreProvider contextId={contextId}>
      <SidebarProvider defaultOpen={true}>
        <ChatSidebar contextId={contextId} />
        <SkipLink href="#main-content">Zum Hauptinhalt springen</SkipLink>
        <SidebarInset className="flex h-dvh flex-col overflow-hidden">
          <ChatHeader contextId={contextId} />
          {children}
        </SidebarInset>
      </SidebarProvider>
    </ChatStoreProvider>
  );
}

export default ExploreLayout;
