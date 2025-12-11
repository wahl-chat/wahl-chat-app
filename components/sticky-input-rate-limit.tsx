'use client';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import LoginButton from '@/components/auth/login-button';
import MessageLoadingBorderTrail from './chat/message-loading-border-trail';
import { useEffect, useRef, useState } from 'react';

type Props = {
  isLoading: boolean;
  onSubmit: (message: string) => void;
  quickReplies?: string[];
  className?: string;
};

function StickyInputRateLimit({
  isLoading,
  onSubmit,
  quickReplies,
  className,
}: Props) {
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

  return (
    <div
      ref={ref}
      className={cn(
        'sticky bottom-[-1px] -mx-2 md:pb-2 pb-4 z-40 transition-all duration-300 ease-out',
        !isSticky && 'mx-0',
        className,
      )}
    >
      <div
        className={cn(
          'relative w-full overflow-hidden rounded-lg border border-input bg-muted py-3 md:py-4',
          'shadow-2xl transition-shadow',
          !isSticky && 'shadow-none',
        )}
      >
        {quickReplies && quickReplies.length > 0 && (
          <div
            className={cn(
              'flex overflow-x-auto gap-1 px-3 md:px-4 whitespace-nowrap [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden',
              isLoading && 'opacity-50 z-0',
            )}
          >
            {quickReplies.map((r) => (
              <button
                key={r}
                className="shrink-0 rounded-full bg-zinc-200 px-2 py-1 transition-colors enabled:hover:bg-zinc-300 disabled:cursor-not-allowed dark:bg-zinc-900 dark:enabled:hover:bg-zinc-950"
                onClick={() => onSubmit(r)}
                disabled={isLoading}
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
            quickReplies && quickReplies.length > 0 && 'mt-2',
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
            <span className="font-bold">melde dich an</span>, um eigene Fragen
            zu stellen.
          </p>
          <LoginButton
            noUserChildren={
              <Button size="sm" className="mt-2">
                Anmelden
              </Button>
            }
          />
        </section>

        {isLoading && <MessageLoadingBorderTrail />}
      </div>
    </div>
  );
}

export default StickyInputRateLimit;
