import { useWahlSwiperStore } from '@/components/providers/wahl-swiper-store-provider';
import WahlSwiperChatMessage from './wahl-swiper-chat-message';
import { useEffect, useRef } from 'react';
import ThinkingMessage from '@/components/chat/thinking-message';
import { MessageCircleMoreIcon } from 'lucide-react';

function WahlSwiperChat() {
  const isFirstRender = useRef(true);
  const messageHistory = useWahlSwiperStore((state) => {
    const currentThesis = state.getCurrentThesis();
    if (!currentThesis) return [];

    return state.messageHistory[currentThesis.id];
  });
  const isLoadingMessage = useWahlSwiperStore((state) => {
    const currentThesis = state.getCurrentThesis();
    if (!currentThesis) return false;

    return state.isLoadingMessage[currentThesis.id];
  });
  const chatContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;

      if (messageHistory.length > 0) {
        chatContainerRef.current?.scrollTo({
          top: chatContainerRef.current.scrollHeight,
          behavior: 'instant',
        });
      }
    }
  }, [messageHistory]);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [messageHistory, isLoadingMessage]);

  return (
    <div className="flex grow overflow-y-auto" ref={chatContainerRef}>
      <div className="flex min-h-fit w-full flex-col gap-6 px-[2px] py-4">
        {messageHistory.length === 0 && (
          <div className="flex grow flex-col items-center justify-center gap-4">
            <MessageCircleMoreIcon className="size-8 text-gray-500" />

            <p className="text-center text-sm text-gray-500">
              Starte eine Konversation zu dieser These um mehr darüber zu
              erfahren.
            </p>
          </div>
        )}

        {messageHistory.map((message) => (
          <WahlSwiperChatMessage key={message.id} message={message} />
        ))}

        {isLoadingMessage && <ThinkingMessage />}
      </div>
    </div>
  );
}

export default WahlSwiperChat;
