import type { MessageItem } from '@/lib/stores/chat-store.types';
import { ChatMessageIcon } from '@/components/chat/chat-message-icon';
import { cn } from '@/lib/utils';
import ChatMarkdown from '@/components/chat/chat-markdown';
import SourcesButton from '@/components/chat/sources-button';
import type { PartyDetails } from '@/lib/party-details';

type Props = {
  message: MessageItem;
  party?: PartyDetails;
};

function ShareSingleMessage({ message, party }: Props) {
  if (message.role === 'user') {
    return (
      <article className="flex flex-col items-end justify-end gap-1">
        <div className="w-fit max-w-[90%] rounded-[20px] bg-muted px-4 py-2 text-foreground">
          {message.content ?? ''}
        </div>
      </article>
    );
  }

  return (
    <article
      id={message.id}
      className={cn(
        'flex flex-col gap-4 relative transition-all duration-200 ease-out',
      )}
    >
      <div className={cn('flex items-start justify-start gap-3 md:gap-4')}>
        <ChatMessageIcon partyId={message.party_id} party={party} />
        <div className="flex flex-col gap-4">
          <ChatMarkdown message={message} />

          <div>
            <SourcesButton
              sources={message.sources ?? []}
              messageContent={message.content ?? ''}
            />
          </div>
        </div>
      </div>
    </article>
  );
}

export default ShareSingleMessage;
