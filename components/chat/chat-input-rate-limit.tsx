'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { cn } from '@/lib/utils';
import { useCallback } from 'react';
import MessageLoadingBorderTrail from './message-loading-border-trail';
import { Button } from '@/components/ui/button';
import LoginButton from '@/components/auth/login-button';

function ChatInputRateLimit() {
  const { user } = useAnonymousAuth();
  const input = useChatStore((state) => state.input);
  const addUserMessage = useChatStore((state) => state.addUserMessage);
  const quickReplies = useChatStore((state) => state.currentQuickReplies);
  const loading = useChatStore((state) => {
    const loading = state.loading;
    return (
      loading.general ||
      loading.newMessage ||
      loading.chatSession ||
      loading.initializingChatSocketSession
    );
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

  const handleQuickReplyClick = (reply: string) => {
    handleSubmit(reply);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="relative w-full overflow-hidden rounded-lg border border-input bg-muted py-3 md:py-4"
    >
      {quickReplies.length > 0 && (
        <div
          className={cn(
            'flex overflow-x-auto gap-1 px-3 md:px-4 whitespace-nowrap [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden',
            loading && 'opacity-50 z-0',
          )}
        >
          {quickReplies.map((r) => (
            <button
              key={r}
              className="shrink-0 rounded-full bg-zinc-200 px-2 py-1 transition-colors enabled:hover:bg-zinc-300 disabled:cursor-not-allowed dark:bg-zinc-900 dark:enabled:hover:bg-zinc-950"
              onClick={() => handleQuickReplyClick(r)}
              disabled={loading}
              type="button"
            >
              <p className="line-clamp-1 text-xs">{r}</p>
            </button>
          ))}
        </div>
      )}

      <section
        className={cn(
          'flex flex-col px-3 md:px-4',
          quickReplies.length > 0 && 'mt-2',
        )}
      >
        <div className="flex items-center gap-2">
          <span className="relative flex size-2">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-yellow-400 opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-yellow-500" />
          </span>
          <h2 className="font-bold">Server derzeit ausgelastet!</h2>
        </div>
        <p className="text-sm text-muted-foreground">
          Chatte mit den vorgeschlagenen Fragen weiter oder{' '}
          <span className="font-bold">melde dich an</span>, um eigene Fragen zu
          stellen.
        </p>
        <LoginButton
          noUserChildren={
            <Button size="sm" className="mt-2">
              Anmelden
            </Button>
          }
        />
      </section>

      {loading && <MessageLoadingBorderTrail />}
    </form>
  );
}

export default ChatInputRateLimit;
