import ChatView from '@/components/chat/chat-view';

type Props = {
  params: Promise<{
    contextId: string;
    chatSessionId: string;
  }>;
  searchParams: Promise<{
    ref_snapshot_id: string;
    q: string;
  }>;
};

async function ChatSessionPage({ params, searchParams }: Props) {
  const { contextId, chatSessionId } = await params;
  const { q } = await searchParams;

  return (
    <ChatView
      sessionId={chatSessionId}
      initialQuestion={q}
      contextId={contextId}
    />
  );
}

export default ChatSessionPage;
