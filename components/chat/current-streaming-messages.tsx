import { useChatStore } from '@/components/providers/chat-store-provider';
import CurrentStreamingMessage from './current-streaming-message';
import ThinkingMessage from './thinking-message';
import { buildCarouselContainerId } from '@/lib/scroll-constants';
import { Button } from '@/components/ui/button';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import Image from 'next/image';
import MessageLoadingBorderTrail from './message-loading-border-trail';
import { useParties } from '@/components/providers/parties-provider';

function CurrentStreamingMessages() {
  const respondingPartyIds = useChatStore(
    (state) => state.currentStreamingMessages?.responding_party_ids,
  );
  const shouldShowThinkingMessage = useChatStore(
    (state) =>
      Object.keys(state.currentStreamingMessages?.messages ?? {}).every(
        (key) =>
          state.currentStreamingMessages?.messages[key].content?.length === 0,
      ) && state.loading.newMessage,
  );

  const id = useChatStore((state) =>
    buildCarouselContainerId(
      Object.values(state.currentStreamingMessages?.messages ?? {}).map(
        (m) => m.id,
      ),
    ),
  );

  const isComplete = useChatStore(
    (state) => state.currentStreamingMessages?.streaming_complete,
  );

  const messageParties = useParties(respondingPartyIds)?.sort((a, b) => {
    const aIndex = respondingPartyIds?.indexOf(a.party_id) ?? 0;
    const bIndex = respondingPartyIds?.indexOf(b.party_id) ?? 0;
    return aIndex - bIndex;
  });

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
    <div
      key={id}
      id={id}
      data-has-message-background
      className="group relative rounded-lg bg-zinc-100 dark:bg-zinc-900"
    >
      <div className="p-4">
        <CurrentStreamingMessage partyId={messageParties?.[0].party_id} />
      </div>
      <div className="mb-4 flex flex-row items-center justify-center gap-4">
        <div className="flex flex-row items-center justify-center gap-2 py-1">
          {messageParties?.map((party, index) => (
            <Button
              key={party.party_id}
              className={cn(
                'size-5 rounded-full bg-zinc-300 overflow-hidden flex items-center justify-center hover:bg-zinc-300 transition-all duration-300 relative',
                index === 0 &&
                  'ring-2 ring-zinc-900 dark:ring-zinc-100 ring-offset-2',
              )}
              style={{
                background: party.background_color,
              }}
              size="icon"
            >
              <Image
                src={buildPartyImageUrl(party.party_id)}
                alt={party.name}
                sizes="20px"
                fill
                className="object-contain"
              />
            </Button>
          ))}
        </div>
      </div>
      <MessageLoadingBorderTrail />
    </div>
  );
}

export default CurrentStreamingMessages;
