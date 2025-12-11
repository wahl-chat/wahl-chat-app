import type { StreamingMessage } from '@/lib/socket.types';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Separator } from '@/components/ui/separator';
import { Eye, EyeClosed, SparkleIcon } from 'lucide-react';
import AnimatedMessageSequence from './animated-message-sequence';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { useEffect, useRef, useState } from 'react';
import { buildVotingBehaviorSeparatorId } from '@/lib/scroll-constants';
import {
  chatViewScrollToVotingBehaviorContainer,
  scrollMessageIntoView,
} from '@/lib/scroll-utils';
import { Markdown } from '@/components/markdown';
import ChatGroupVotingBehaviorEmblaReinit from './chat-group-voting-behavior-embla-reinit';
import type { ChatVotingBehaviorDetailButtonRef } from './chat-voting-behavior-detail-button';
import ChatVotingBehaviorDetailButton from './chat-voting-behavior-detail-button';

type Props = {
  message: MessageItem | StreamingMessage;
  isGroupChat?: boolean;
};

function ChatVotingBehaviorExpandable({ message, isGroupChat }: Props) {
  const [isExpanded, setIsExpanded] = useState(!message.voting_behavior);
  const isLoadingVotingBehaviorSummary = useChatStore(
    (state) => state.loading.votingBehaviorSummary === message.id,
  );
  const shouldShowVotingBehaviorSummary = useChatStore(
    (state) =>
      state.currentStreamedVotingBehavior?.requestId === message.id ||
      message.voting_behavior?.summary,
  );
  const votingBehavior = useChatStore((state) =>
    state.currentStreamedVotingBehavior?.requestId === message.id
      ? state.currentStreamedVotingBehavior
      : message.voting_behavior,
  );
  const [
    prevIsLoadingVotingBehaviorSummary,
    setPrevIsLoadingVotingBehaviorSummary,
  ] = useState(isLoadingVotingBehaviorSummary);
  const votingBehaviorDetailButtonRef =
    useRef<ChatVotingBehaviorDetailButtonRef>(null);

  const isFirstRender = useRef(true);

  useEffect(() => {
    if (!prevIsLoadingVotingBehaviorSummary && isLoadingVotingBehaviorSummary) {
      setIsExpanded(true);
    }

    setPrevIsLoadingVotingBehaviorSummary(isLoadingVotingBehaviorSummary);
  }, [
    isLoadingVotingBehaviorSummary,
    message.id,
    message.voting_behavior,
    prevIsLoadingVotingBehaviorSummary,
  ]);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    if (isExpanded) {
      chatViewScrollToVotingBehaviorContainer(message.id);
    } else {
      scrollMessageIntoView(message.id);
    }
  }, [isExpanded, message.id]);

  if (!shouldShowVotingBehaviorSummary) {
    return null;
  }

  const emblaReinitComponent = isGroupChat ? (
    <ChatGroupVotingBehaviorEmblaReinit
      messageId={message.id}
      isExpanded={isExpanded}
    />
  ) : null;

  if (isLoadingVotingBehaviorSummary && !votingBehavior?.summary) {
    return (
      <>
        <Separator />
        <div className="flex items-center gap-4">
          <SparkleIcon className="size-4 animate-spin text-muted-foreground [animation-duration:4s]" />

          <AnimatedMessageSequence
            className="text-muted-foreground"
            messages={[
              'Durchsuche Bundestags-Anträge...',
              'Durchsuche Abstimmungsprotokolle...',
              'Analysiere Antragsteller-Informationen...',
              'Vergleiche Informationen...',
              'Ergebnisse zusammenfassen...',
            ]}
          />
        </div>
        {emblaReinitComponent}
      </>
    );
  }

  const onReferenceClick = (voteId: number) => {
    votingBehaviorDetailButtonRef.current?.open(voteId.toString());
  };

  const getReferenceTooltip = (voteId: number) => {
    const voteIdString = voteId.toString();
    return (
      votingBehavior?.votes?.find((vote) => vote.id === voteIdString)?.title ??
      null
    );
  };

  const getReferenceName = (voteId: number) => {
    return `Abst. ${voteId}`;
  };

  return (
    <>
      <Separator id={buildVotingBehaviorSeparatorId(message.id)} />
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleContent>
          <Markdown
            onReferenceClick={onReferenceClick}
            getReferenceTooltip={getReferenceTooltip}
            getReferenceName={getReferenceName}
          >
            {votingBehavior?.summary ?? ''}
          </Markdown>
        </CollapsibleContent>
        <div
          className={cn(
            'flex flex-row items-center justify-between mt-0',
            isExpanded && 'mt-4',
          )}
        >
          {!isExpanded ? (
            <p className="text-xs text-muted-foreground">
              Diese Nachricht enthält weitere Informationen zum{' '}
              <span className="font-bold">Abstimmungsverhalten</span> der
              Partei.
            </p>
          ) : message.voting_behavior ? (
            <ChatVotingBehaviorDetailButton
              votingBehavior={message.voting_behavior}
              ref={votingBehaviorDetailButtonRef}
              partyId={message.party_id ?? ''}
            />
          ) : (
            <div />
          )}
          <Tooltip>
            <CollapsibleTrigger asChild>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="aspect-square">
                  {isExpanded ? <EyeClosed /> : <Eye />}
                </Button>
              </TooltipTrigger>
            </CollapsibleTrigger>
            <TooltipContent>
              {isExpanded ? 'Verbergen' : 'Anzeigen'}
            </TooltipContent>
          </Tooltip>
        </div>
      </Collapsible>
      {emblaReinitComponent}
    </>
  );
}

export default ChatVotingBehaviorExpandable;
