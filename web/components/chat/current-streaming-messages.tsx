import { useChatStore } from '@/components/providers/chat-store-provider';
import { useContextParties } from '@/components/providers/context-provider';
import {
  Carousel,
  type CarouselApi,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '@/components/ui/carousel';
import { buildCarouselContainerId } from '@/lib/scroll-constants';
import AutoHeight from 'embla-carousel-auto-height';
import { useEffect, useMemo, useState } from 'react';
import ChatGroupSlideCounter from './chat-group-slide-counter';
import CurrentStreamingMessage from './current-streaming-message';
import MessageLoadingBorderTrail from './message-loading-border-trail';
import ThinkingMessage from './thinking-message';

const AUTO_HEIGHT_REINIT_MS = 200;

function CurrentStreamingMessages() {
  const respondingPartyIds = useChatStore(
    (state) => state.currentStreamingMessages?.responding_party_ids,
  );
  const streamingTurnId = useChatStore(
    (state) => state.currentStreamingMessages?.id,
  );
  const shouldShowThinkingMessage = useChatStore(
    (state) =>
      Object.keys(state.currentStreamingMessages?.messages ?? {}).every(
        (key) =>
          state.currentStreamingMessages?.messages[key].content?.length === 0,
      ) && state.loading.newMessage,
  );

  const containerId = useChatStore((state) =>
    buildCarouselContainerId(
      Object.values(state.currentStreamingMessages?.messages ?? {}).map(
        (m) => m.id,
      ),
    ),
  );

  const isComplete = useChatStore(
    (state) => state.currentStreamingMessages?.streaming_complete,
  );

  // Select the messages record (stable until the store mutates it). Deriving
  // a new object inside the Zustand selector would break useSyncExternalStore
  // getSnapshot identity and loop into "Maximum update depth exceeded".
  const streamingMessages = useChatStore(
    (state) => state.currentStreamingMessages?.messages,
  );
  const statusByPartyId = useMemo(() => {
    if (!streamingMessages) return undefined;
    return Object.fromEntries(
      Object.entries(streamingMessages).map(([partyId, message]) => [
        partyId,
        {
          chunking_complete: message.chunking_complete,
          failed: message.failed,
        },
      ]),
    );
  }, [streamingMessages]);

  const messageParties = useContextParties(respondingPartyIds)?.sort((a, b) => {
    const aIndex = respondingPartyIds?.indexOf(a.party_id) ?? 0;
    const bIndex = respondingPartyIds?.indexOf(b.party_id) ?? 0;
    return aIndex - bIndex;
  });

  const [carouselApi, setCarouselApi] = useState<CarouselApi>();

  useEffect(() => {
    if (!carouselApi || isComplete) return;
    const intervalId = window.setInterval(() => {
      carouselApi.reInit();
    }, AUTO_HEIGHT_REINIT_MS);
    return () => window.clearInterval(intervalId);
  }, [carouselApi, isComplete]);

  if (shouldShowThinkingMessage) {
    return <ThinkingMessage />;
  }

  if (!respondingPartyIds || !messageParties) {
    return null;
  }

  if (isComplete) {
    return null;
  }

  if (respondingPartyIds.length === 1) {
    return <CurrentStreamingMessage partyId={respondingPartyIds[0]} />;
  }

  return (
    <Carousel
      key={streamingTurnId}
      id={containerId}
      data-has-message-background
      className="group relative rounded-lg bg-zinc-100 dark:bg-zinc-900"
      plugins={[AutoHeight()]}
      setApi={setCarouselApi}
    >
      <CarouselContent>
        {messageParties.map((party) => (
          <CarouselItem key={party.party_id}>
            <div className="p-4">
              <CurrentStreamingMessage partyId={party.party_id} />
            </div>
          </CarouselItem>
        ))}
      </CarouselContent>
      <div className="mb-4 flex flex-row items-center justify-center gap-4">
        <CarouselPrevious />
        <ChatGroupSlideCounter
          parties={messageParties}
          containerId={containerId}
          statusByPartyId={statusByPartyId}
        />
        <CarouselNext />
      </div>
      <MessageLoadingBorderTrail />
    </Carousel>
  );
}

export default CurrentStreamingMessages;
