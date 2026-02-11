'use client';

import MessageLoadingBorderTrail from '@/components/chat/message-loading-border-trail';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import { useCallback, useRef, useState } from 'react';
import TextareaAutosize from 'react-textarea-autosize';

interface Props {
  onSubmit: (message: string) => void;
}

const MAX_ROWS = 5;

export default function AgentChatInput({ onSubmit }: Props) {
  const input = useAgentStore((state) => state.input);
  const setInput = useAgentStore((state) => state.setInput);
  const isStreaming = useAgentStore((state) => state.isStreaming);
  const singleLineHeight = useRef(0);
  const [isMultiLine, setIsMultiLine] = useState(false);

  const handleHeightChange = useCallback(
    (height: number, meta: { rowHeight: number }) => {
      if (singleLineHeight.current === 0) {
        singleLineHeight.current = height;
      }
      setIsMultiLine(height > singleLineHeight.current + meta.rowHeight / 2);
    },
    [],
  );

  const handleSubmit = useCallback(() => {
    if (!input.trim() || isStreaming) return;

    onSubmit(input.trim());
    setInput('');
  }, [input, isStreaming, onSubmit, setInput]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const submitButton = (
    <Button
      type="submit"
      disabled={!input.trim() || isStreaming}
      className={cn(
        'flex size-8 items-center justify-center rounded-full',
        'bg-foreground text-background transition-colors hover:bg-foreground/80',
        'disabled:bg-foreground/20 disabled:text-muted',
      )}
      size="icon"
    >
      <ArrowUp className="size-4 font-bold" />
    </Button>
  );

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        handleSubmit();
      }}
      className={cn(
        'relative w-full overflow-hidden rounded-[24px] border border-input bg-chat-input transition-colors',
        'focus-within:border-zinc-300 dark:focus-within:border-zinc-700',
      )}
    >
      <div className="relative">
        <TextareaAutosize
          className={cn(
            'block min-h-0 w-full resize-none border-0 bg-chat-input py-3 pl-4 text-[16px] leading-[1.5] shadow-none ring-0 focus-visible:ring-0 focus-visible:ring-offset-0',
            'placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed',
            'pr-12',
          )}
          minRows={1}
          maxRows={MAX_ROWS}
          onHeightChange={handleHeightChange}
          placeholder="Gib hier deine Nachricht ein..."
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          value={input}
          disabled={isStreaming}
          maxLength={3000}
        />
        {!isMultiLine && (
          <div className="absolute bottom-2 right-2">{submitButton}</div>
        )}
      </div>

      {isMultiLine && (
        <div className="flex justify-end px-2 pb-2">{submitButton}</div>
      )}

      {isStreaming && <MessageLoadingBorderTrail />}
    </form>
  );
}
