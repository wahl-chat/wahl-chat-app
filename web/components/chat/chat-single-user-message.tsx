import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import { RotateCcwIcon } from 'lucide-react';
import { toast } from 'sonner';

export const INITIAL_MESSAGE_ID = 'initial-question';

type Props = {
  message: MessageItem;
  isLastMessage: boolean;
};

function ChatSingleUserMessage({ message, isLastMessage }: Props) {
  const shouldShowResendButton = useChatStore((state) => {
    if (message.id === INITIAL_MESSAGE_ID) {
      return state.initialQuestionError === message.content;
    }

    return isLastMessage && !state.loading.newMessage;
  });
  const addUserMessage = useChatStore((state) => state.addUserMessage);
  const { user } = useAnonymousAuth();

  const handleResendMessage = () => {
    if (!user) {
      toast.error(
        'Bitte lade die Seite neu, um eine Nachricht erneut zu senden.',
      );
      return;
    }

    addUserMessage(user.uid, message.content ?? '');
  };

  return (
    <article className="flex flex-col items-end justify-end gap-1">
      <div className="w-fit max-w-[90%] rounded-[20px] bg-muted px-4 py-2 text-foreground">
        {message.content ?? ''}
      </div>
      {shouldShowResendButton && (
        <Button
          onClick={handleResendMessage}
          className="h-6 gap-1 p-0 px-2 text-xs text-red-500 hover:bg-red-500/10 hover:text-red-400"
          variant="ghost"
        >
          <RotateCcwIcon className="!size-3" />
          Erneut senden
        </Button>
      )}
    </article>
  );
}

export default ChatSingleUserMessage;
