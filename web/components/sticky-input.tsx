'use client';

import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import Logo from './chat/logo';
import MessageLoadingBorderTrail from './chat/message-loading-border-trail';
import AutoGrowTextarea from './ui/auto-grow-textarea';
import { Button } from './ui/button';

// The visual viewport is this much shorter than the window: a keyboard.
const KEYBOARD_PX = 120;

/** While the box is focused with an on-screen keyboard open, the top edge of
 * the area between the box and the keyboard; null otherwise. */
function useKeyboardGap(
  ref: React.RefObject<HTMLDivElement | null>,
  focused: boolean,
): number | null {
  const [top, setTop] = useState<number | null>(null);
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!focused || !viewport) {
      setTop(null);
      return;
    }
    const measure = () => {
      // A pinch zoom shrinks the visual viewport too; only a keyboard does at scale 1.
      const open =
        window.innerHeight - viewport.height * viewport.scale > KEYBOARD_PX;
      const node = ref.current;
      setTop(open && node ? node.getBoundingClientRect().bottom : null);
    };
    measure();
    viewport.addEventListener('resize', measure);
    viewport.addEventListener('scroll', measure);
    // The box moves with the page when it is not stuck to the bottom.
    window.addEventListener('scroll', measure, { passive: true });
    return () => {
      viewport.removeEventListener('resize', measure);
      viewport.removeEventListener('scroll', measure);
      window.removeEventListener('scroll', measure);
    };
  }, [ref, focused]);
  return top;
}

type Props = {
  isLoading: boolean;
  onSubmit: (message: string) => void;
  quickReplies?: string[];
  placeholder?: string;
  className?: string;
};

function StickyInput({
  isLoading,
  onSubmit,
  quickReplies,
  placeholder = 'Frage die Parteien...',
  className,
}: Props) {
  const [input, setInput] = useState('');
  const [isSticky, setIsSticky] = useState(true);
  const [focused, setFocused] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const gapTop = useKeyboardGap(ref, focused);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const onIn = () => setFocused(true);
    const onOut = (event: FocusEvent) => {
      if (!node.contains(event.relatedTarget as Node | null)) {
        setFocused(false);
      }
    };
    node.addEventListener('focusin', onIn);
    node.addEventListener('focusout', onOut);
    return () => {
      node.removeEventListener('focusin', onIn);
      node.removeEventListener('focusout', onOut);
    };
  }, []);

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

  const handleSubmit = (e?: React.FormEvent<HTMLFormElement>) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;
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
      {/* With the keyboard open, what lies below the box shows above the
          keyboard; cover it while typing. Fixed, so the page does not grow. */}
      {gapTop !== null && (
        <div
          aria-hidden
          className="pointer-events-none fixed inset-x-0 bottom-0"
          style={{
            top: gapTop,
            background: 'var(--daily-canvas, hsl(var(--background)))',
          }}
        />
      )}
      <form
        onSubmit={handleSubmit}
        className={cn(
          'relative shadow-2xl transition-shadow duration-300 max-w-xl mx-auto w-full grid overflow-hidden rounded-[20px] border border-input dark:focus-within:border-zinc-700 focus-within:border-zinc-300 bg-chat-input ease-out md:shadow-none',
          !isSticky && 'shadow-none',
        )}
      >
        {isLoading && <MessageLoadingBorderTrail />}

        {quickReplies && quickReplies.length > 0 && (
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
          className="absolute bottom-2 left-2 size-8 translate-y-0 rounded-full border border-border p-1"
        />
        <AutoGrowTextarea
          className="w-full bg-chat-input px-12 py-3 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed"
          name="question"
          placeholder={placeholder}
          aria-label={placeholder}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onSubmit={() => handleSubmit()}
          maxLength={500}
        />
        <Button
          type="submit"
          className={cn(
            'absolute right-2 bottom-2 translate-y-0 flex size-8 items-center justify-center rounded-full bg-foreground text-background transition-colors hover:bg-foreground/80 disabled:bg-foreground/20 disabled:text-muted',
          )}
          disabled={!input.length || isLoading}
          aria-label="Frage senden"
        >
          <ArrowUp className="size-4 font-bold" />
        </Button>
      </form>
    </div>
  );
}

export default StickyInput;
