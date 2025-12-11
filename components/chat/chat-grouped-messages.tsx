import { useChatStore } from '@/components/providers/chat-store-provider';
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '@/components/ui/carousel';
import type { PartyDetails } from '@/lib/party-details';
import { buildCarouselContainerId } from '@/lib/scroll-constants';
import type {
  GroupedMessage,
  MessageItem,
} from '@/lib/stores/chat-store.types';
import AutoHeight from 'embla-carousel-auto-height';
import ChatGroupSlideCounter from './chat-group-slide-counter';
import ChatSingleMessage from './chat-single-message';
import MessageLoadingBorderTrail from './message-loading-border-trail';
import SurveyBanner from './survey-banner';

type Props = {
  message: GroupedMessage;
  isLastMessage?: boolean;
  showAssistantIcon?: boolean;
  parties?: PartyDetails[];
};

function ChatGroupedMessages({ message, isLastMessage, parties }: Props) {
  const isLoadingAnyAction = useChatStore(
    (state) =>
      state.loading.proConPerspective === message.id ||
      state.loading.votingBehaviorSummary === message.id,
  );

  if (message.messages.length === 1) {
    return (
      <ChatSingleMessage
        message={message.messages[0]}
        partyId={message.messages[0].party_id}
        party={parties?.find(
          (p) => p.party_id === message.messages[0].party_id,
        )}
        isLastMessage={isLastMessage}
        voiceTranscriptionStatus={message.voice_transcription}
      />
    );
  }

  const messagePartiesDict = message.messages
    .map((msg) => ({
      message: msg,
      party: parties?.find((p) => p.party_id === msg.party_id),
    }))
    .filter(({ party }) => party !== undefined) as {
    party: PartyDetails;
    message: MessageItem;
  }[];

  const id = buildCarouselContainerId(message.messages.map((m) => m.id));

  return (
    <Carousel
      key={id}
      id={id}
      data-has-message-background
      className="group relative rounded-lg bg-zinc-100 dark:bg-zinc-900"
      plugins={[AutoHeight()]}
    >
      <CarouselContent>
        {messagePartiesDict?.map(({ message: innerMessage, party }) => {
          return (
            <CarouselItem key={innerMessage.id}>
              <div className="p-4">
                <ChatSingleMessage
                  message={innerMessage}
                  party={party}
                  partyId={innerMessage.party_id}
                  showAssistantIcon={true}
                  isGroupChat
                />
              </div>
            </CarouselItem>
          );
        })}
      </CarouselContent>

      <div className="mb-4 flex flex-row items-center justify-center gap-4">
        <CarouselPrevious />
        <ChatGroupSlideCounter
          parties={messagePartiesDict?.map(({ party }) => party) ?? []}
          containerId={id}
        />
        <CarouselNext />
      </div>
      {isLastMessage && <SurveyBanner />}
      {isLoadingAnyAction && <MessageLoadingBorderTrail />}
    </Carousel>
  );
}

export default ChatGroupedMessages;
