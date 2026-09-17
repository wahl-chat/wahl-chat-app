import { useChatStore } from '@/components/providers/chat-store-provider';
import type { PartyDetails } from '@/lib/party-details';
import { isProlificStudy } from '@/lib/prolific-study/prolific-metadata';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';
import ChatMarkdown from './chat-markdown';
import { ChatMessageIcon } from './chat-message-icon';
import ChatPledgeTracker from './chat-pledge-tracker';
import ChatProConExpandable from './chat-pro-con-expandable';
import ChatSingleMessageActions from './chat-single-message-actions';
import ChatSingleUserMessage from './chat-single-user-message';
import ChatVotingBehaviorExpandable from './chat-voting-behavior-expandable';
import MessageLoadingBorderTrail from './message-loading-border-trail';
import SurveyBanner from './survey-banner';

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

  // PledgeTracker opens as a popup (dialog/drawer), not an in-message
  // expandable — deliberately NOT part of shouldHaveBackground.
  const [pledgeOpen, setPledgeOpen] = useState(false);
  const setPledgeModalOpen = useChatStore((state) => state.setPledgeModalOpen);
  const recordStudyEvent = useChatStore((state) => state.recordStudyEvent);

  // The popup's open state also feeds the store: the study's questionnaire
  // prompt must never fire while the modal is open (and fires on its close),
  // and open/close pairs belong to the participant's interaction log.
  const handlePledgeOpenChange = (open: boolean) => {
    setPledgeOpen(open);
    setPledgeModalOpen(open);
    void recordStudyEvent(open ? 'pledge_modal_open' : 'pledge_modal_close');
  };

  // Unmounting while open must not leave the store flag stuck (only one
  // popup can be open at a time, so clearing on unmount is always safe).
  useEffect(() => () => setPledgeModalOpen(false), [setPledgeModalOpen]);

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
            {isLastMessage && !isProlificStudy() && <SurveyBanner />}
            <ChatSingleMessageActions
              isLastMessage={isLastMessage}
              message={message}
              partyId={partyId}
              showMessageActions={showMessageActions}
              isGroupChat={isGroupChat}
              pledgeRevealed={pledgeOpen}
              onTogglePledgeTracker={() => handlePledgeOpenChange(!pledgeOpen)}
            />
          </div>
        </div>
        <ChatProConExpandable message={message} isGroupChat={isGroupChat} />
        <ChatVotingBehaviorExpandable
          message={message}
          isGroupChat={isGroupChat}
        />
        <ChatPledgeTracker
          message={message}
          open={pledgeOpen}
          onOpenChange={handlePledgeOpenChange}
        />
        {isLoadingAnyAction && !isGroupChat && <MessageLoadingBorderTrail />}
      </article>
    );
  }

  return <ChatMarkdown message={message} />;
}

ChatSingleMessage.displayName = 'ChatSingleMessage';

export default ChatSingleMessage;
