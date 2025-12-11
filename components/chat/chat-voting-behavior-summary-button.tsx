import { Button } from '@/components/ui/button';
import { VoteIcon } from 'lucide-react';
import { useChatStore } from '@/components/providers/chat-store-provider';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import type { StreamingMessage } from '@/lib/socket.types';
import { useParty } from '@/components/providers/parties-provider';
import ChatActionButtonHighlight from './chat-action-button-highlight';
import { track } from '@vercel/analytics/react';

type Props = {
  partyId: string;
  message: MessageItem | StreamingMessage;
  isLastMessage?: boolean;
};

function ChatVotingBehaviorSummaryButton({
  partyId,
  message,
  isLastMessage,
}: Props) {
  const party = useParty(partyId);
  const generateVotingBehaviorSummary = useChatStore(
    (state) => state.generateVotingBehaviorSummary,
  );
  const clickedVotingBehaviorSummaryButton = useChatStore(
    (state) => state.clickedVotingBehaviorSummaryButton,
  );

  const handleGenerateVotingBehaviorSummary = async () => {
    track('voting_behavior_summary_button_clicked', {
      party: partyId,
      message: message.content ?? 'empty-message',
    });
    generateVotingBehaviorSummary(partyId, message);
  };

  const showHighlight = isLastMessage && !clickedVotingBehaviorSummaryButton;

  if (party?.is_already_in_parliament === false) return null;

  return (
    <div className="relative rounded-md">
      <Button
        variant="outline"
        className="h-8 px-2 group-data-[has-message-background]:bg-zinc-100 group-data-[has-message-background]:hover:bg-zinc-200 group-data-[has-message-background]:dark:bg-zinc-900 group-data-[has-message-background]:dark:hover:bg-zinc-800"
        tooltip="Analysiere das Abstimmungsverhalten der Partei"
        onClick={handleGenerateVotingBehaviorSummary}
      >
        <VoteIcon />
        <span className="text-xs">Abstimmungsverhalten</span>
      </Button>

      <ChatActionButtonHighlight showHighlight={showHighlight} />
    </div>
  );
}

export default ChatVotingBehaviorSummaryButton;
