'use client';

import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import Logo from './chat/logo';
import MessageLoadingBorderTrail from './chat/message-loading-border-trail';
import { Button } from './ui/button';

type Props = {
  isLoading: boolean;
  onSubmit: (message: string) => void;
  quickReplies?: string[];
  className?: string;
};

function StickyInput({ isLoading, onSubmit, quickReplies, className }: Props) {
  const [input, setInput] = useState('');
  const [isSticky, setIsSticky] = useState(true);
  const ref = useRef<HTMLDivElement>(null);

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
    onSubmit(input);
  };

  const handleQuickReplyClick = (reply: string) => {
    onSubmit(reply);
  };

  return (
    <div
      ref={ref}
      className={cn(
        'sticky bottom-[-1px] -mx-2 md:pb-2 pb-4 z-40 transition-all duration-300 ease-out',
        !isSticky && 'mx-0',
        className,
      )}
    >
      <form
        onSubmit={handleSubmit}
        className={cn(
          'relative shadow-2xl transition-shadow duration-300 max-w-xl mx-auto w-full grid overflow-hidden rounded-[20px] border border-input dark:focus-within:border-zinc-700 focus-within:border-zinc-300 bg-chat-input ease-out md:shadow-none',
          !isSticky && 'shadow-none',
        )}
      >
        {isLoading && <MessageLoadingBorderTrail />}

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

        <Logo
          variant="small"
          className="absolute bottom-2 left-2 size-8 translate-y-0 rounded-full border border-border p-1"
        />
        <input
          className="w-full bg-chat-input px-12 py-3 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed"
          name="question"
          placeholder="Frage die Parteien..."
          value={input}
          type="text"
          onChange={(e) => setInput(e.target.value)}
          maxLength={500}
        />
        <Button
          type="submit"
          className={cn(
            'absolute right-2 bottom-2 translate-y-0 flex size-8 items-center justify-center rounded-full bg-foreground text-background transition-colors hover:bg-foreground/80 disabled:bg-foreground/20 disabled:text-muted',
          )}
          disabled={!input.length || isLoading}
        >
          <ArrowUp className="size-4 font-bold" />
        </Button>
      </form>
    </div>
  );
}

export default StickyInput;
