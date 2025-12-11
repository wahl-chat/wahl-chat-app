import { useChatStore } from '@/components/providers/chat-store-provider';
import { ChatMessageIcon } from './chat-message-icon';
import ChatProConExpandable from './chat-pro-con-expandable';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import ChatMarkdown from './chat-markdown';
import ChatSingleMessageActions from './chat-single-message-actions';
import { cn } from '@/lib/utils';
import ChatVotingBehaviorExpandable from './chat-voting-behavior-expandable';
import MessageLoadingBorderTrail from './message-loading-border-trail';
import ChatSingleUserMessage from './chat-single-user-message';
import SurveyBanner from './survey-banner';
import type { PartyDetails } from '@/lib/party-details';

type Props = {
  message: MessageItem;
  partyId?: string;
  party?: PartyDetails;
  isLastMessage?: boolean;
  showAssistantIcon?: boolean;
  showMessageActions?: boolean;
  isGroupChat?: boolean;
};

function ChatSingleMessage({
  message,
  partyId,
  party,
  isLastMessage,
  showAssistantIcon = true,
  showMessageActions = true,
  isGroupChat = false,
}: Props) {
  const isLoadingAnyAction = useChatStore(
    (state) =>
      state.loading.proConPerspective === message.id ||
      state.loading.votingBehaviorSummary === message.id,
  );

  const shouldHaveBackground =
    message.pro_con_perspective ||
    message.voting_behavior ||
    isLoadingAnyAction;

  const content = (
    <div className="flex flex-col gap-4">
      <ChatMarkdown message={message} />
    </div>
  );

  if (message.role === 'user') {
    return (
      <ChatSingleUserMessage
        message={message}
        isLastMessage={isLastMessage ?? false}
      />
    );
  }

  if (message.role === 'assistant') {
    return (
      <article
        id={message.id}
        className={cn(
          'flex flex-col gap-4 relative transition-all duration-200 ease-out',
          shouldHaveBackground && 'bg-zinc-100 dark:bg-zinc-900 group',
          !isGroupChat &&
            shouldHaveBackground &&
            'border border-muted p-3 md:p-4 rounded-lg',
        )}
        data-has-message-background={Boolean(shouldHaveBackground)}
      >
        <div className={cn('flex items-start justify-start gap-3 md:gap-4')}>
          {showAssistantIcon && (
            <ChatMessageIcon partyId={partyId} party={party} />
          )}
          <div className="flex flex-col gap-2">
            {content}
            {isLastMessage && <SurveyBanner />}
            <ChatSingleMessageActions
              isLastMessage={isLastMessage}
              message={message}
              partyId={partyId}
              showMessageActions={showMessageActions}
              isGroupChat={isGroupChat}
            />
          </div>
        </div>
        <ChatProConExpandable message={message} isGroupChat={isGroupChat} />
        <ChatVotingBehaviorExpandable
          message={message}
          isGroupChat={isGroupChat}
        />
        {isLoadingAnyAction && !isGroupChat && <MessageLoadingBorderTrail />}
      </article>
    );
  }

  return <ChatMarkdown message={message} />;
}

ChatSingleMessage.displayName = 'ChatSingleMessage';

export default ChatSingleMessage;
