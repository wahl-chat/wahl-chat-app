import { useChatStore } from '@/components/providers/chat-store-provider';
import ChatMarkdown from './chat-markdown';

type Props = {
  partyId: string;
};

function ChatSingleStreamingMessageContent({ partyId }: Props) {
  const message = useChatStore(
    (state) => state.currentStreamingMessages?.messages[partyId],
  );

  if (!message) {
    return null;
  }

  return <ChatMarkdown message={message} />;
}

export default ChatSingleStreamingMessageContent;
