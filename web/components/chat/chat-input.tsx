'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { useCurrentContext } from '@/components/providers/context-provider';
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

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
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
        quickReplies?.length > 0 && 'rounded-[20px]',
      )}
    >
      {quickReplies.length > 0 && (
        <>
          {!isGeneral && <ChatInputAddPartiesButton disabled={loading} />}
          <div
            className={cn(
              !isGeneral && 'ml-7',
              'flex gap-1 px-2 pt-2 overflow-x-auto whitespace-nowrap [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden',
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
        <div
          className={cn(
            'absolute left-2 z-40 top-1/2 -translate-y-1/2',
            quickReplies.length > 0 && 'top-auto bottom-3 translate-y-0',
          )}
        >
          <ChatInputGeneralMenu disabled={loading} />
        </div>
      )}

      <input
        className={cn(
          'w-full bg-chat-input py-3 pl-4 pr-11 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed',
          isGeneral && 'pl-11',
        )}
        placeholder="Schreibe eine Nachricht..."
        onChange={handleChange}
        value={input}
        disabled={loading}
        maxLength={500}
      />
      <Button
        type="submit"
        disabled={!input.length || loading}
        className={cn(
          'absolute right-2 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-full bg-foreground text-background transition-colors hover:bg-foreground/80 disabled:bg-foreground/20 disabled:text-muted',
          quickReplies.length > 0 && 'bottom-0 translate-y-0',
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
      {form}
    </div>
  );
}

export default ChatInput;
