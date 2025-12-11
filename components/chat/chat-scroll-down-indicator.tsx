'use client';

import { chatViewScrollToBottom } from '@/lib/scroll-utils';
import { cn } from '@/lib/utils';
import { ArrowDownIcon } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { SCROLL_CONTAINER_ID } from '@/lib/scroll-constants';

function ChatScrollDownIndicator() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (!document) return;

    const scrollContainer = document.getElementById(SCROLL_CONTAINER_ID);
    if (!scrollContainer) return;

    const handleScroll = () => {
      const isScrolled =
        scrollContainer.scrollTop +
          scrollContainer.clientHeight -
          scrollContainer.scrollHeight <
        -1;
      setIsVisible(isScrolled);
    };

    scrollContainer.addEventListener('scroll', handleScroll);
    scrollContainer.addEventListener('resize', handleScroll);

    return () => {
      scrollContainer.removeEventListener('scroll', handleScroll);
      scrollContainer.removeEventListener('resize', handleScroll);
    };
  }, [isVisible]);

  const handleClick = () => {
    chatViewScrollToBottom();
  };

  return (
    <div
      className={cn(
        'absolute inset-x-4 -top-10 flex justify-end pointer-events-none',
      )}
    >
      <Button
        variant="default"
        className={cn(
          'size-8 rounded-full shadow-xl bg-background dark:bg-zinc-900 border border-border hover:bg-zinc-100 dark:hover:bg-muted',
          'transition-all duration-200 ease-in-out z-40',
          'md:hover:scale-110 md:hover:-translate-y-1',
          isVisible
            ? 'opacity-100 translate-y-0 scale-100 pointer-events-auto'
            : 'opacity-0 translate-y-2 scale-0 pointer-events-none',
        )}
        onClick={handleClick}
        size="icon"
      >
        <ArrowDownIcon className="size-4 text-muted-foreground" />
      </Button>
    </div>
  );
}

export default ChatScrollDownIndicator;
