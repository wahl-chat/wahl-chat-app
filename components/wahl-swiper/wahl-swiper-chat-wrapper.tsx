'use client';

import { cn } from '@/lib/utils';
import { useEffect, useRef, useState } from 'react';
import WahlSwiperInput from './wahl-swiper-input';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import WahlSwiperChat from './wahl-swiper-chat';
import VisuallyHidden from '@/components/visually-hidden';
import { useWahlSwiperStore } from '@/components/providers/wahl-swiper-store-provider';
import { Separator } from '@/components/ui/separator';

function WahlSwiperChatWrapper() {
  const shouldShowChat = useWahlSwiperStore(
    (state) => state.thesesStack.length > 0,
  );
  const [isSticky, setIsSticky] = useState(true);
  const chatIsExpanded = useWahlSwiperStore((state) => state.chatIsExpanded);
  const setChatIsExpanded = useWahlSwiperStore(
    (state) => state.setChatIsExpanded,
  );
  const currentThesis = useWahlSwiperStore((state) => state.getCurrentThesis());
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

  const handleToggleExpand = () => {
    setChatIsExpanded(!chatIsExpanded);
  };

  if (!shouldShowChat) return null;

  return (
    <ResponsiveDialog open={chatIsExpanded} onOpenChange={setChatIsExpanded}>
      <div
        ref={ref}
        className={cn(
          'sticky bottom-[-1px] -mx-2 mt-6 md:pb-2 pb-4 z-40 transition-all duration-300 ease-out',
          !isSticky && 'mx-0',
        )}
      >
        <WahlSwiperInput
          isSticky={isSticky}
          handleToggleExpand={handleToggleExpand}
          handleNewMessage={() => setChatIsExpanded(true)}
        />
      </div>

      <ResponsiveDialogContent className="flex h-[95dvh] w-full flex-col md:max-w-xl">
        <ResponsiveDialogHeader>
          <ResponsiveDialogTitle className="whitespace-normal text-sm md:max-w-[95%] md:text-base">
            {currentThesis?.question}
          </ResponsiveDialogTitle>
          <VisuallyHidden>
            <ResponsiveDialogDescription>
              Chatte mit dem Wahl-Swiper
            </ResponsiveDialogDescription>
          </VisuallyHidden>
        </ResponsiveDialogHeader>

        <Separator />

        <div className="mt-2 flex grow flex-col overflow-y-hidden px-2 pb-4 md:mt-0 md:p-1">
          <WahlSwiperChat />

          <WahlSwiperInput
            isSticky={false}
            handleToggleExpand={handleToggleExpand}
          />
        </div>
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default WahlSwiperChatWrapper;
