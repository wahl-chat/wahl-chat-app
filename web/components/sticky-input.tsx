'use client';

import QuestionTopicIcon from '@/components/question-topic-icon';
import { cn } from '@/lib/utils';
import { ArrowUp, ArrowUpRight, LoaderCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import Logo from './chat/logo';
import MessageLoadingBorderTrail from './chat/message-loading-border-trail';
import { Button } from './ui/button';

export type StickyInputAppearance = 'default' | 'hero';

export type StickyInputDraftProps = {
  value?: string;
  onValueChange?: (value: string) => void;
  focusRequest?: number;
};

type Props = StickyInputDraftProps & {
  isLoading: boolean;
  canSubmit?: boolean;
  notice?: React.ReactNode;
  onSubmit: (message: string) => void;
  quickReplies?: string[];
  quickReplyTopics?: Record<string, string>;
  className?: string;
  appearance?: StickyInputAppearance;
  headerActions?: React.ReactNode;
  footerActions?: React.ReactNode;
};

function StickyInput({
  isLoading,
  onSubmit,
  quickReplies,
  quickReplyTopics,
  className,
  appearance = 'default',
  headerActions,
  footerActions,
  value,
  onValueChange,
  focusRequest = 0,
  canSubmit = true,
  notice,
}: Props) {
  const [localInput, setLocalInput] = useState('');
  const input = value ?? localInput;
  const setInput = onValueChange ?? setLocalInput;
  const [hoveredReply, setHoveredReply] = useState<string | null>(null);
  const [focusedReply, setFocusedReply] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
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

  useEffect(() => {
    if (!focusRequest || !isHero) return;
    setHoveredReply(null);
    setFocusedReply(null);
    textareaRef.current?.focus({ preventScroll: true });
    textareaRef.current?.scrollIntoView({
      block: 'center',
      behavior: 'instant',
    });
  }, [focusRequest, isHero]);

  useEffect(() => {
    setHoveredReply(null);
    setFocusedReply(null);
  }, [quickReplies]);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim() || isLoading || !canSubmit) return;

    onSubmit(input);
  };

  const handleQuickReplyClick = (reply: string) => {
    if (isLoading) return;
    if (isHero) {
      setInput(reply.slice(0, 500));
      setHoveredReply(null);
      setFocusedReply(null);
      textareaRef.current?.focus();
      return;
    }
    onSubmit(reply);
  };

  const handleHeroKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter' || e.shiftKey || e.nativeEvent.isComposing) return;

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
        aria-busy={isLoading}
        className={cn(
          'relative shadow-2xl transition-shadow duration-300 max-w-xl mx-auto w-full grid overflow-hidden rounded-[20px] border border-input dark:focus-within:border-zinc-700 focus-within:border-zinc-300 bg-chat-input ease-out md:shadow-none',
          isHero &&
            'max-w-none rounded-3xl border-white/80 bg-white/50 backdrop-blur-xl backdrop-saturate-150 shadow-[inset_0_1px_0_rgba(255,255,255,0.65),0_12px_40px_-16px_rgba(70,30,30,0.16)] focus-within:border-white focus-within:ring-4 focus-within:ring-foreground/5 md:shadow-[inset_0_1px_0_rgba(255,255,255,0.65),0_12px_40px_-16px_rgba(70,30,30,0.16)] dark:border-white/15 dark:bg-zinc-950/50 dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_12px_40px_-16px_rgba(0,0,0,0.4)] dark:focus-within:border-white/25',
          !isHero && !isSticky && 'shadow-none',
        )}
      >
        {isLoading && <MessageLoadingBorderTrail />}
        <fieldset disabled={isLoading} className="contents">
          {!isHero && (
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
          {!isHero && (
            <Logo
              variant="small"
              className="absolute bottom-2 left-2 size-8 rounded-full border border-border p-1"
            />
          )}
          {isHero ? (
            <div className="relative">
              <span
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
              >
                <Logo
                  variant="small"
                  className="size-7 rounded-full border border-border/40 bg-background/50 p-1"
                />
              </span>
              <textarea
                ref={textareaRef}
                className="block max-h-48 min-h-16 w-full resize-none bg-transparent py-5 pl-12 pr-3 text-base leading-6 [field-sizing:content] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed"
                name="question"
                aria-label="Deine politische Frage"
                placeholder={
                  hoveredReply ?? focusedReply ?? 'Was möchtest du wissen?'
                }
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleHeroKeyDown}
                enterKeyHint="send"
                maxLength={500}
                rows={1}
                readOnly={isLoading}
                aria-describedby="composer-status"
              />
            </div>
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
          {isHero ? (
            <div className="flex items-center justify-between gap-2 px-3 pb-2">
              <div className="min-w-0">{footerActions}</div>
              <Button
                type="submit"
                disabled={!input.trim() || isLoading || !canSubmit}
                aria-label="Frage stellen"
                title="Frage stellen"
                className="size-8 shrink-0 rounded-full bg-foreground p-0 text-background transition-colors hover:bg-foreground/80 disabled:bg-muted disabled:text-muted-foreground disabled:opacity-100"
              >
                {isLoading ? (
                  <LoaderCircle
                    className="size-4 animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <ArrowUp className="size-4" aria-hidden="true" />
                )}
              </Button>
            </div>
          ) : (
            <Button
              type="submit"
              aria-label="Frage stellen"
              className="absolute bottom-2 right-2 flex size-8 items-center justify-center rounded-full bg-foreground text-background hover:bg-foreground/80 disabled:bg-foreground/20 disabled:text-muted"
              disabled={!input.trim() || isLoading || !canSubmit}
            >
              <ArrowUp className="size-4" aria-hidden="true" />
            </Button>
          )}
          {isHero && headerActions && (
            <div className="flex min-w-0 items-center border-t border-border/30 bg-white/20 px-3 py-1.5 dark:bg-white/[0.03]">
              {headerActions}
            </div>
          )}
        </fieldset>
        {isHero && (
          <div
            id="composer-status"
            role="status"
            className="px-6 text-xs text-muted-foreground"
          >
            {!isLoading && notice ? <div className="py-3">{notice}</div> : null}
          </div>
        )}
      </form>

      {isHero && quickReplies && quickReplies.length > 0 && (
        <div
          className="mt-3 flex flex-col gap-0.5 text-sm text-muted-foreground"
          aria-label="Beispielfragen"
        >
          <span className="sr-only">Zum Beispiel</span>
          {quickReplies.slice(0, 3).map((reply) => (
            <Button
              key={reply}
              variant="ghost"
              className="group h-auto w-full justify-start gap-3 whitespace-normal rounded-xl border border-transparent p-2 text-left text-sm font-normal leading-relaxed hover:border-border/60 hover:bg-muted/30 sm:gap-4 sm:text-base"
              type="button"
              onClick={() => handleQuickReplyClick(reply)}
              onMouseEnter={() => setHoveredReply(reply)}
              onMouseLeave={() => setHoveredReply(null)}
              onFocus={() => setFocusedReply(reply)}
              onBlur={() => setFocusedReply(null)}
              title={reply}
              disabled={isLoading}
            >
              <span className="flex size-8 shrink-0 items-center justify-center rounded-xl border border-border/50 bg-muted/30 text-muted-foreground transition-colors group-hover:border-border group-hover:bg-background group-hover:text-foreground">
                <QuestionTopicIcon
                  topic={quickReplyTopics?.[reply]}
                  className="size-[18px]"
                />
              </span>
              <span className="flex-1">{reply}</span>
              <ArrowUpRight
                className="size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-70 group-focus-visible:opacity-70"
                aria-hidden="true"
              />
            </Button>
          ))}
        </div>
      )}
    </div>
  );
}

export default StickyInput;
