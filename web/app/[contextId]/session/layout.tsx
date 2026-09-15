import AnonymousUserChatStoreUpdater from '@/components/auth/anonymous-user-chat-store-updater';
import ChatHeader from '@/components/chat/chat-header';
import ChatStudyDevBar from '@/components/chat/chat-study-dev-bar';
import ChatSidebar from '@/components/chat/sidebar/chat-sidebar';
import { ChatStoreProvider } from '@/components/providers/chat-store-provider';
import SseChatProvider from '@/components/providers/sse-chat-provider';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import type { Metadata } from 'next';

// Covers both /[contextId]/session and /[contextId]/session/[chatSessionId]: chat
// sessions are user-generated and must never be indexed.
export const metadata: Metadata = {
  robots: 'noindex, nofollow',
};

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
      <SseChatProvider>
        <SidebarProvider defaultOpen={true}>
          <ChatSidebar contextId={contextId} />
          <SidebarInset className="flex h-dvh flex-col overflow-hidden">
            <ChatHeader contextId={contextId} />
            {/* Outer gate; the component checks STUDY_DEV_TOOLS again. The
                bar can therefore never render outside local dev — but note the
                module is still emitted into the client bundle, because a
                'use client' import from a server component becomes a client
                reference that survives tree-shaking. ~1KB of inert code. */}
            {process.env.NODE_ENV === 'development' && <ChatStudyDevBar />}
            {children}
          </SidebarInset>
        </SidebarProvider>
      </SseChatProvider>
    </ChatStoreProvider>
  );
}

export default SessionLayout;
