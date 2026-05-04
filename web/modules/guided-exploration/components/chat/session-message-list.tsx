'use client';

import { MessageCitationsList } from '@/modules/guided-exploration/components/shared/message-citations-list';
import { PartyMarkedMarkdown } from '@/modules/guided-exploration/components/shared/party-marked-markdown';
import type { SessionMessage } from '@/modules/guided-exploration/types';
import { useCitationHandlers } from '@/modules/guided-exploration/utils';

import { ExplorationTreeCard } from './exploration-tree-card';
import { TopicDirectionsCard } from './topic-directions-card';

interface SessionMessageListProps {
  messages: SessionMessage[];
  onOpenLeafAction?: (explorationId: string, leafId: string) => void;
  onDirectionChoiceAction?: (
    queryId: string,
    directions: Array<{ id: string; name: string }>,
  ) => void;
  isLoading?: boolean;
  lastUserMessageIndex?: number;
  lastUserMessageRef?: React.RefObject<HTMLDivElement | null>;
  /** Minimum number of directions the user must select */
  minDirections?: number;
  /** Owning tree of the deep-link leaf, used to scope `deepLinkLeafId`. */
  deepLinkExplorationId?: string | null;
  /** Leaf id from a `?leaf=<id>` deep link, forwarded to the matching card. */
  deepLinkLeafId?: string | null;
}

export function SessionMessageList({
  messages,
  onOpenLeafAction,
  onDirectionChoiceAction,
  isLoading = false,
  lastUserMessageIndex = -1,
  lastUserMessageRef,
  minDirections,
  deepLinkExplorationId,
  deepLinkLeafId,
}: SessionMessageListProps) {
  return (
    <div
      className="space-y-4"
      aria-live="polite"
      aria-atomic="false"
      aria-relevant="additions"
    >
      {messages.map((message, index) => {
        if (message.type === 'user') {
          const isLastUser = index === lastUserMessageIndex;
          return (
            <div
              key={message.id}
              ref={isLastUser ? lastUserMessageRef : undefined}
              className="flex justify-end"
            >
              <div className="max-w-[80%] rounded-[20px] bg-muted px-4 py-2">
                <span className="sr-only">Deine Nachricht: </span>
                <p className="text-sm">{message.content}</p>
              </div>
            </div>
          );
        }

        if (message.type === 'assistant') {
          return <AssistantSessionMessage key={message.id} message={message} />;
        }

        if (message.type === 'exploration_start') {
          const ownsDeepLink =
            !!deepLinkLeafId &&
            !!deepLinkExplorationId &&
            message.explorationId === deepLinkExplorationId;
          return (
            <ExplorationTreeCard
              key={message.id}
              message={message}
              onOpenLeaf={onOpenLeafAction}
              deepLinkLeafId={ownsDeepLink ? deepLinkLeafId : null}
            />
          );
        }

        if (message.type === 'topic_directions' && message.directions) {
          return (
            <TopicDirectionsCard
              key={message.id}
              directions={{
                type: 'topic_directions',
                queryId: message.directionsQueryId ?? '',
                originalQuery: '',
                directions: message.directions,
              }}
              onSelectDirections={(directions) =>
                onDirectionChoiceAction?.(
                  message.directionsQueryId ?? '',
                  directions,
                )
              }
              isLoading={isLoading || !onDirectionChoiceAction}
              selectedDirections={message.selectedDirections}
              minSelections={minDirections}
            />
          );
        }

        return null;
      })}
    </div>
  );
}

function AssistantSessionMessage({ message }: { message: SessionMessage }) {
  const citations = message.citations ?? [];
  const { getReferenceName, getReferenceTooltip, handleReferenceClick } =
    useCitationHandlers(citations);

  return (
    <div>
      <span className="sr-only">Antwort der KI: </span>
      <PartyMarkedMarkdown
        onReferenceClick={handleReferenceClick}
        getReferenceName={getReferenceName}
        getReferenceTooltip={getReferenceTooltip}
      >
        {message.content ?? ''}
      </PartyMarkedMarkdown>
      <MessageCitationsList citations={citations} messageId={message.id} />
    </div>
  );
}
