import { useChatStore } from '@/components/providers/chat-store-provider';
import { Separator } from '@/components/ui/separator';
import { WAHL_CHAT_PARTY_ID } from '@/lib/constants';
import { getVisiblePledges } from '@/lib/pledge-tracker/pledges';
import type { StreamingMessage } from '@/lib/socket.types';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import ChatMessageLikeDislikeButtons from './chat-message-like-dislike-buttons';
import ChatPledgeTrackerButton from './chat-pledge-tracker-button';
import ChatProConButton from './chat-pro-con-button';
import ChatVotingBehaviorSummaryButton from './chat-voting-behavior-summary-button';
import CopyButton from './copy-button';
import SourcesButton from './sources-button';

type Props = {
  message: MessageItem | StreamingMessage;
  isLastMessage?: boolean;
  showMessageActions?: boolean;
  partyId?: string;
  isGroupChat?: boolean;
  pledgeRevealed?: boolean;
  onTogglePledgeTracker?: () => void;
};

function ChatSingleMessageActions({
  isLastMessage,
  message,
  showMessageActions,
  partyId,
  pledgeRevealed,
  onTogglePledgeTracker,
}: Props) {
  const isLoadingProConPerspective = useChatStore(
    (state) => state.loading.proConPerspective === message.id,
  );
  const isLoadingVotingBehaviorSummary = useChatStore(
    (state) => state.loading.votingBehaviorSummary === message.id,
  );

  if (!showMessageActions) return null;

  const isWahlChatMessage = partyId === WAHL_CHAT_PARTY_ID;

  const showProConButton =
    partyId &&
    !message.pro_con_perspective &&
    !isLoadingProConPerspective &&
    !isWahlChatMessage;

  const showVotingBehaviorSummaryButton =
    partyId &&
    !message.voting_behavior &&
    !isLoadingVotingBehaviorSummary &&
    !isWahlChatMessage;

  // Same filter as the popup, so the button never opens an empty timeline.
  const showPledgeTrackerButton =
    partyId &&
    getVisiblePledges(message.pledge_tracker).length > 0 &&
    !isWahlChatMessage;

  const showSeparator =
    showProConButton ||
    showVotingBehaviorSummaryButton ||
    showPledgeTrackerButton;

  return (
    <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
      <SourcesButton
        sources={message.sources ?? []}
        messageContent={message.content ?? ''}
      />
      {showProConButton && (
        <ChatProConButton
          partyId={partyId}
          message={message}
          isLastMessage={isLastMessage}
        />
      )}

      {showVotingBehaviorSummaryButton && (
        <ChatVotingBehaviorSummaryButton
          partyId={partyId}
          message={message}
          isLastMessage={isLastMessage}
        />
      )}

      {showPledgeTrackerButton && (
        <ChatPledgeTrackerButton
          partyId={partyId}
          message={message}
          revealed={pledgeRevealed}
          onToggle={onTogglePledgeTracker}
        />
      )}

      {showSeparator && (
        <Separator
          orientation="vertical"
          className="ml-2 hidden h-6 sm:block"
        />
      )}

      <div className="flex items-center">
        <CopyButton
          text={message.content ?? ''}
          variant="ghost"
          size="icon"
          className="size-8"
        />
        <ChatMessageLikeDislikeButtons message={message} />
      </div>
    </div>
  );
}

export default ChatSingleMessageActions;
