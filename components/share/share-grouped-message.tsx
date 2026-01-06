'use client';

import ChatGroupSlideCounter from '@/components/chat/chat-group-slide-counter';
import {
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '@/components/ui/carousel';
import { Carousel } from '@/components/ui/carousel';
import type { PartyDetails } from '@/lib/party-details';
import type {
  GroupedMessage,
  MessageItem,
} from '@/lib/stores/chat-store.types';
import AutoHeight from 'embla-carousel-auto-height';
import ShareSingleMessage from './share-single-message';

type Props = {
  message: GroupedMessage;
  parties: PartyDetails[];
};

function ShareGroupedMessage({ message, parties }: Props) {
  if (message.role === 'user') {
    return <ShareSingleMessage message={message.messages[0]} />;
  }

  if (message.messages.length === 1) {
    return <ShareSingleMessage message={message.messages[0]} />;
  }

  const messagePartiesDict = parties
    .map((party) => ({
      party,
      message: message.messages.find((m) => m.party_id === party.party_id),
    }))
    .filter(({ message }) => message !== undefined) as {
    party: PartyDetails;
    message: MessageItem;
  }[];

  return (
    <Carousel
      id={message.id}
      data-has-message-background
      className="group relative rounded-lg bg-zinc-100 dark:bg-zinc-900"
      plugins={[AutoHeight()]}
    >
      <CarouselContent>
        {messagePartiesDict?.map(({ message, party }) => {
          return (
            <CarouselItem key={message.id}>
              <div className="p-4">
                <ShareSingleMessage message={message} party={party} />
              </div>
            </CarouselItem>
          );
        })}
      </CarouselContent>

      <div className="mb-4 flex flex-row items-center justify-center gap-4">
        <CarouselPrevious />
        <ChatGroupSlideCounter parties={parties} containerId={message.id} />
        <CarouselNext />
      </div>
    </Carousel>
  );
}

export default ShareGroupedMessage;
