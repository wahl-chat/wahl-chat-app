'use client';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import type { StreamingMessage } from '@/lib/socket.types';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import { track } from '@vercel/analytics/react';
import ChatActionButtonHighlight from './chat-action-button-highlight';
import ProConIcon from './pro-con-icon';

type Props = {
  partyId: string;
  message: MessageItem | StreamingMessage;
  isLastMessage?: boolean;
};

function ChatProConButton({ partyId, message, isLastMessage }: Props) {
  const generateProConPerspective = useChatStore(
    (state) => state.generateProConPerspective,
  );
  const clickedProConButton = useChatStore(
    (state) => state.clickedProConButton,
  );

  const handleGenerateProConPerspective = async () => {
    track('pro_con_button_clicked', {
      party: partyId,
      message: message.content ?? 'empty-message',
    });
    await generateProConPerspective(partyId, message);
  };

  const showHighlight = isLastMessage && !clickedProConButton;

  return (
    <div className="relative rounded-md">
      <Button
        variant="outline"
        className="h-8 px-2 group-data-[has-message-background]:bg-zinc-100 group-data-[has-message-background]:hover:bg-zinc-200 group-data-[has-message-background]:dark:bg-zinc-900 group-data-[has-message-background]:dark:hover:bg-zinc-800"
        tooltip="Ordne die Position in Pro oder Contra ein"
        onClick={handleGenerateProConPerspective}
      >
        <ProConIcon />
        <span className="text-xs">Position einordnen</span>
      </Button>
      <ChatActionButtonHighlight showHighlight={showHighlight} />
    </div>
  );
}

export default ChatProConButton;
