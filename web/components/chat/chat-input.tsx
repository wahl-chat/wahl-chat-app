'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { useCurrentContext } from '@/components/providers/context-provider';
import AutoGrowTextarea from '@/components/ui/auto-grow-textarea';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import { useCallback } from 'react';
import ChatFocusChips from './chat-focus-chips';
import ChatInputAddPartiesButton from './chat-input-add-parties-button';
import ChatInputGeneralMenu from './chat-input-general-menu';
import MessageLoadingBorderTrail from './message-loading-border-trail';

function ChatInput() {
  const { user } = useAnonymousAuth();
  const input = useChatStore((state) => state.input);
  const setInput = useChatStore((state) => state.setInput);
  const addUserMessage = useChatStore((state) => state.addUserMessage);
  const quickReplies = useChatStore((state) => state.currentQuickReplies);
  const isGeneral = useCurrentContext({ optional: true })?.type === 'general';
  const loading = useChatStore((state) => {
    const loading = state.loading;
    return loading.general || loading.newMessage || loading.chatSession;
  });

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement> | string) => {
      let effectiveInput = input;

      if (typeof e === 'string') {
        effectiveInput = e;
      } else {
        e.preventDefault();
      }

      if (!user?.uid || !effectiveInput.trim()) return;

      addUserMessage(user.uid, effectiveInput);
    },
    [user?.uid, input, addUserMessage],
  );

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  const handleQuickReplyClick = (reply: string) => {
    handleSubmit(reply);
  };

  const form = (
    <form
      onSubmit={handleSubmit}
      className={cn(
        'relative w-full overflow-hidden rounded-[30px] border border-input dark:focus-within:border-zinc-700 focus-within:border-zinc-300 transition-colors bg-chat-input',
        !isGeneral && quickReplies.length > 0 && 'rounded-[20px]',
        isGeneral && 'rounded-[24px]',
      )}
    >
      {!isGeneral && quickReplies.length > 0 && (
        <>
          <ChatInputAddPartiesButton disabled={loading} />
          <div
            className={cn(
              'ml-7 flex gap-1 px-2 pt-2 overflow-x-auto whitespace-nowrap [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden',
              loading && 'opacity-50 z-0',
            )}
          >
            {quickReplies.map((r) => (
              <button
                key={r}
                className="shrink-0 rounded-full bg-muted px-2 py-1 transition-colors enabled:hover:bg-muted/50 disabled:cursor-not-allowed"
                onClick={() => handleQuickReplyClick(r)}
                disabled={loading}
                type="button"
              >
                <p className="line-clamp-1 text-xs">{r}</p>
              </button>
            ))}
          </div>
        </>
      )}

      {loading && <MessageLoadingBorderTrail />}

      {isGeneral && (
        <div className="absolute bottom-3 left-2 z-40">
          <ChatInputGeneralMenu disabled={loading} />
        </div>
      )}

      <AutoGrowTextarea
        className={cn(
          'w-full bg-chat-input py-3 pl-4 pr-11 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed',
          isGeneral && 'pl-11',
        )}
        placeholder="Schreibe eine Nachricht..."
        aria-label="Nachricht"
        onChange={handleChange}
        onSubmit={() => handleSubmit(input)}
        value={input}
        disabled={loading}
        maxLength={500}
      />
      <Button
        type="submit"
        disabled={!input.length || loading}
        className={cn(
          'absolute right-2 bottom-2 flex size-8 items-center justify-center rounded-full bg-foreground text-background transition-colors hover:bg-foreground/80 disabled:bg-foreground/20 disabled:text-muted',
        )}
      >
        <ArrowUp className="size-4 font-bold" />
      </Button>
    </form>
  );

  if (!isGeneral) {
    return form;
  }

  return (
    <div className="flex w-full flex-col">
      <ChatFocusChips disabled={loading} />
      {quickReplies.length > 0 && (
        <div
          className={cn(
            '-mx-3 mb-2 flex gap-1.5 overflow-x-auto whitespace-nowrap px-3 md:mx-0 md:px-0 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden',
            loading && 'opacity-50',
          )}
        >
          {quickReplies.map((r) => (
            <button
              key={r}
              className="shrink-0 rounded-full border border-input bg-background px-3 py-1.5 shadow-sm transition-colors enabled:hover:bg-muted disabled:cursor-not-allowed"
              onClick={() => handleQuickReplyClick(r)}
              disabled={loading}
              type="button"
            >
              <p className="line-clamp-1 text-xs">{r}</p>
            </button>
          ))}
        </div>
      )}
      {form}
    </div>
  );
}

export default ChatInput;
