import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import type {
  MessageItem,
  VoiceTranscriptionStatus,
} from '@/lib/stores/chat-store.types';
import { AlertCircle, Mic, RotateCcwIcon } from 'lucide-react';
import { toast } from 'sonner';

export const INITIAL_MESSAGE_ID = 'initial-question';

// Subcomponent: Pending transcription skeleton
function VoiceTranscriptionPending() {
  return (
    <div className="flex items-center gap-2">
      <Mic className="size-4 animate-pulse text-muted-foreground" />
      <div className="flex flex-col gap-1">
        <div className="h-4 w-32 animate-pulse rounded bg-muted-foreground/20" />
        <div className="h-4 w-20 animate-pulse rounded bg-muted-foreground/20" />
      </div>
    </div>
  );
}

// Subcomponent: Transcription error
function VoiceTranscriptionError() {
  return (
    <div className="w-fit max-w-[90%] rounded-[20px] bg-red-100 px-4 py-2 dark:bg-red-900/30">
      <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
        <AlertCircle className="size-4" />
        <span className="text-sm">
          Fehler bei der Sprache-zu-Text Übersetzung. Bitte versuche es erneut.
        </span>
      </div>
    </div>
  );
}

// Subcomponent: Transcribed message content
function TranscribedMessageContent({ content }: { content: string }) {
  return (
    <div className="flex flex-col gap-1">
      {content}
      <span className="text-xs text-muted-foreground">Sprache-zu-Text</span>
    </div>
  );
}

// Subcomponent: Regular message bubble
function MessageBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="w-fit max-w-[90%] rounded-[20px] bg-muted px-4 py-2 text-foreground">
      {children}
    </div>
  );
}

type Props = {
  message: MessageItem;
  isLastMessage: boolean;
  voiceTranscriptionStatus?: VoiceTranscriptionStatus;
};

function ChatSingleUserMessage({
  message,
  isLastMessage,
  voiceTranscriptionStatus,
}: Props) {
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

  const isPending = voiceTranscriptionStatus?.status === 'pending';
  const isError = voiceTranscriptionStatus?.status === 'error';
  const isTranscribed = voiceTranscriptionStatus?.status === 'transcribed';

  const renderContent = () => {
    if (isPending) {
      return (
        <MessageBubble>
          <VoiceTranscriptionPending />
        </MessageBubble>
      );
    }

    if (isError) {
      return <VoiceTranscriptionError />;
    }

    if (isTranscribed) {
      return (
        <MessageBubble>
          <TranscribedMessageContent content={message.content ?? ''} />
        </MessageBubble>
      );
    }

    // Regular message
    return <MessageBubble>{message.content ?? ''}</MessageBubble>;
  };

  return (
    <article className="flex flex-col items-end justify-end gap-1">
      {renderContent()}
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
