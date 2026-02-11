'use client';
import { ThumbsUp } from 'lucide-react';

import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import type { StreamingMessage } from '@/lib/socket.types';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import { cn } from '@/lib/utils';
import { track } from '@vercel/analytics/react';
import ChatDislikeFeedbackButton from './chat-dislike-feedback-button';

type Props = {
  message: MessageItem | StreamingMessage;
};

function ChatMessageLikeDislikeButtons({ message }: Props) {
  const setMessageFeedback = useChatStore((state) => state.setMessageFeedback);

  const handleLike = () => {
    track('message_liked', {
      message: message.content ?? 'empty-message',
    });
    setMessageFeedback(message.id, { feedback: 'like' });
  };

  const handleDislikeFeedback = (details: string) => {
    setMessageFeedback(message.id, { feedback: 'dislike', detail: details });
    track('message_disliked', {
      message: message.content ?? 'empty-message',
      details,
    });
  };

  const isLiked = message.feedback?.feedback === 'like';
  const isDisliked = message.feedback?.feedback === 'dislike';

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        className="group/like size-8 group-data-[has-message-background=true]:hover:bg-zinc-200 group-data-[has-message-background=true]:dark:hover:bg-zinc-800"
        onClick={handleLike}
      >
        <div className="group-hover/like:-translate-y-2 group-hover/like:scale-125 group-hover/like:transition-transform group-hover/like:duration-200 group-hover/like:ease-in-out">
          <ThumbsUp className={cn(isLiked && 'fill-foreground/30')} />
        </div>
      </Button>
      <ChatDislikeFeedbackButton
        isDisliked={isDisliked}
        onDislikeFeedback={handleDislikeFeedback}
        feedbackDetail={message.feedback?.detail}
      />
    </>
  );
}

export default ChatMessageLikeDislikeButtons;
