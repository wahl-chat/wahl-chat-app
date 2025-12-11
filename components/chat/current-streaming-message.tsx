import { useChatStore } from '@/components/providers/chat-store-provider';
import { cn } from '@/lib/utils';
import { ChatMessageIcon } from './chat-message-icon';
import ChatSingleStreamingMessageContent from './chat-single-streaming-message-content';

type Props = {
  partyId: string;
};

function CurrentStreamingMessage({ partyId }: Props) {
  const messageId = useChatStore(
    (state) => state.currentStreamingMessages?.messages[partyId].id,
  );

  if (!messageId) {
    return null;
  }

  return (
    <article id={messageId} className={cn('flex flex-row gap-3 md:gap-4')}>
      <ChatMessageIcon partyId={partyId} />
      <div className="flex flex-col gap-2">
        <div className="flex flex-col gap-4">
          <ChatSingleStreamingMessageContent partyId={partyId} />
        </div>
      </div>
    </article>
  );
}

export default CurrentStreamingMessage;
