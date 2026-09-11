'use client';

import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import Logo from './chat/logo';
import MessageLoadingBorderTrail from './chat/message-loading-border-trail';
import { Button } from './ui/button';

export type StickyInputAppearance = 'default' | 'hero';

type Props = {
  isLoading: boolean;
  onSubmit: (message: string) => void;
  quickReplies?: string[];
  className?: string;
  appearance?: StickyInputAppearance;
  headerActions?: React.ReactNode;
  footerActions?: React.ReactNode;
};

function StickyInput({
  isLoading,
  onSubmit,
  quickReplies,
  className,
  appearance = 'default',
  headerActions,
  footerActions,
}: Props) {
  const [input, setInput] = useState('');
  const [isSticky, setIsSticky] = useState(true);
  const ref = useRef<HTMLDivElement>(null);
  const isHero = appearance === 'hero';

  useEffect(() => {
    const cachedRef = ref.current;

    if (!cachedRef) return;

    const observer = new IntersectionObserver(
      ([e]) => setIsSticky(e.intersectionRatio < 1),
      { threshold: 1 },
    );

    observer.observe(cachedRef);

    return () => {
      observer.unobserve(cachedRef);
    };
  }, [ref]);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    onSubmit(input);
  };

  const handleQuickReplyClick = (reply: string) => {
    onSubmit(reply);
  };

  const handleHeroKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter' || (!e.metaKey && !e.ctrlKey)) return;

    e.preventDefault();
    e.currentTarget.form?.requestSubmit();
  };

  return (
    <div
      ref={ref}
      className={cn(
        !isHero &&
          'sticky bottom-[-1px] -mx-2 z-40 pb-4 transition-all duration-300 ease-out md:pb-2',
        !isHero && !isSticky && 'mx-0',
        className,
      )}
    >
      <form
        onSubmit={handleSubmit}
        className={cn(
          'relative shadow-2xl transition-shadow duration-300 max-w-xl mx-auto w-full grid overflow-hidden rounded-[20px] border border-input dark:focus-within:border-zinc-700 focus-within:border-zinc-300 bg-chat-input ease-out md:shadow-none',
          isHero && 'max-w-none shadow-none',
          !isHero && !isSticky && 'shadow-none',
        )}
      >
        {isLoading && <MessageLoadingBorderTrail />}

        {isHero ? (
          headerActions && (
            <div className="flex gap-1 overflow-x-auto whitespace-nowrap px-2 pt-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {headerActions}
            </div>
          )
        ) : (
          <div className="flex gap-1 overflow-x-auto whitespace-nowrap px-2 pt-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {quickReplies?.map((reply) => {
              return (
                <button
                  key={reply}
                  className={cn(
                    'shrink-0 rounded-full bg-muted px-2 py-1 transition-colors enabled:hover:bg-muted/70 disabled:cursor-not-allowed disabled:opacity-50',
                  )}
                  type="button"
                  onClick={() => handleQuickReplyClick(reply)}
                >
                  <p className="line-clamp-1 text-xs">{reply}</p>
                </button>
              );
            })}
          </div>
        )}

        <Logo
          variant="small"
          className={cn(
            'absolute left-2 size-8 rounded-full border border-border p-1',
            isHero ? 'top-12' : 'bottom-2 translate-y-0',
          )}
        />
        {isHero ? (
          <textarea
            className="min-h-28 w-full resize-none bg-chat-input px-12 py-4 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed"
            name="question"
            aria-label="Deine politische Frage"
            placeholder="Frage die Parteien..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleHeroKeyDown}
            maxLength={500}
            rows={3}
          />
        ) : (
          <input
            className="w-full bg-chat-input px-12 py-3 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed"
            name="question"
            aria-label="Deine politische Frage"
            placeholder="Frage die Parteien..."
            value={input}
            type="text"
            onChange={(e) => setInput(e.target.value)}
            maxLength={500}
          />
        )}
        <Button
          type="submit"
          aria-label="Frage stellen"
          className={cn(
            'absolute right-2 bottom-2 translate-y-0 flex size-8 items-center justify-center rounded-full bg-foreground text-background transition-colors hover:bg-foreground/80 disabled:bg-foreground/20 disabled:text-muted',
          )}
          disabled={!input.trim() || isLoading}
        >
          <ArrowUp className="size-4 font-bold" aria-hidden="true" />
        </Button>
      </form>

      {isHero && footerActions}

      {isHero && quickReplies && quickReplies.length > 0 && (
        <div
          className="mt-3 flex items-center gap-2 overflow-x-auto whitespace-nowrap pb-1 text-xs text-muted-foreground [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
          aria-label="Beispielfragen"
        >
          <span className="shrink-0">Zum Beispiel</span>
          {quickReplies.slice(0, 3).map((reply) => (
            <Button
              key={reply}
              variant="outline"
              size="sm"
              className="h-9 max-w-64 shrink-0 rounded-full px-3 font-normal"
              type="button"
              onClick={() => handleQuickReplyClick(reply)}
              disabled={isLoading}
            >
              <span className="truncate">{reply}</span>
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

export default StickyInput;
