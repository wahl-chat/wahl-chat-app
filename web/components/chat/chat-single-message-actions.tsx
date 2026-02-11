import { useChatStore } from '@/components/providers/chat-store-provider';
import { Separator } from '@/components/ui/separator';
import { WAHL_CHAT_PARTY_ID } from '@/lib/constants';
import type { StreamingMessage } from '@/lib/socket.types';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import ChatMessageLikeDislikeButtons from './chat-message-like-dislike-buttons';
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
};

function ChatSingleMessageActions({
  isLastMessage,
  message,
  showMessageActions,
  partyId,
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

  const showSeparator = showProConButton || showVotingBehaviorSummaryButton;

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
