'use client';

import { buildProConPerspectiveSeparatorId } from '@/lib/scroll-constants';
import {
  chatViewScrollToProConPerspectiveContainer,
  scrollMessageIntoView,
} from '@/lib/scroll-utils';
import type { MessageItem } from '@/lib/stores/chat-store.types';
import { cn, prettifiedUrlName } from '@/lib/utils';
import { ArrowUpDown, Eye, EyeClosed, SparkleIcon } from 'lucide-react';
import { useEffect, useState, useRef } from 'react';
import { Markdown } from '@/components/markdown';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import AnimatedMessageSequence from './animated-message-sequence';
import type { StreamingMessage } from '@/lib/socket.types';
import ChatGroupProConEmblaReinit from './chat-group-pro-con-embla-reinit';

type Props = {
  message: MessageItem | StreamingMessage;
  isGroupChat?: boolean;
};

function ChatProConExpandable({ message, isGroupChat }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);
  const isLoadingProConPerspective = useChatStore(
    (state) => state.loading.proConPerspective === message.id,
  );
  const [prevIsLoadingProConPerspective, setPrevIsLoadingProConPerspective] =
    useState(isLoadingProConPerspective);

  const proConMessage = message.pro_con_perspective;

  const isFirstRender = useRef(true);

  useEffect(() => {
    if (prevIsLoadingProConPerspective && !isLoadingProConPerspective) {
      setIsExpanded(true);
    }
    setPrevIsLoadingProConPerspective(isLoadingProConPerspective);
  }, [
    isLoadingProConPerspective,
    message.pro_con_perspective,
    message.id,
    prevIsLoadingProConPerspective,
  ]);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    if (isExpanded) {
      chatViewScrollToProConPerspectiveContainer(message.id);
    } else {
      scrollMessageIntoView(message.id);
    }
  }, [isExpanded, message.id]);

  const emblaReinitComponent = isGroupChat ? (
    <ChatGroupProConEmblaReinit
      messageId={message.id}
      isExpanded={isExpanded}
    />
  ) : null;

  if (isLoadingProConPerspective) {
    return (
      <>
        <Separator />
        <div className="flex items-center gap-4">
          <SparkleIcon className="size-4 animate-spin text-muted-foreground [animation-duration:4s]" />

          <AnimatedMessageSequence
            className="text-muted-foreground"
            messages={[
              'Thema verstehen...',
              'Machbarkeit analysieren...',
              'Kurzfristige Effekte identifizieren...',
              'Langfristige Effekte identifizieren...',
              'Analyse abschließen...',
            ]}
          />
        </div>
        {emblaReinitComponent}
      </>
    );
  }

  if (!proConMessage) {
    return null;
  }

  const onReferenceClick = (number: number) => {
    if (number < 0 || number >= proConMessage.sources.length) {
      return;
    }

    const source = proConMessage.sources[number];
    window.open(source.source, '_blank');
  };

  const getReferenceTooltip = (number: number) => {
    if (number < 0 || number >= proConMessage.sources.length) {
      return null;
    }

    const source = proConMessage.sources[number];
    if (!source) {
      return null;
    }

    return source.source;
  };

  const getReferenceName = (number: number) => {
    if (number < 0 || number >= proConMessage.sources.length) {
      return null;
    }

    const source = proConMessage.sources[number];
    if (!source) {
      return null;
    }

    return prettifiedUrlName(source.source);
  };

  return (
    <>
      <Separator id={buildProConPerspectiveSeparatorId(message.id)} />
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleContent asChild>
          <Markdown
            getReferenceTooltip={getReferenceTooltip}
            getReferenceName={getReferenceName}
            onReferenceClick={onReferenceClick}
          >
            {proConMessage.content}
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
              Diese Nachricht enthält eine{' '}
              <span className="font-bold">eingeordnete Position</span>.
            </p>
          ) : (
            <span className="flex flex-row items-center gap-2 text-xs text-muted-foreground">
              <ArrowUpDown className="size-4" />
              Scrolle für mehr
            </span>
          )}
          <Tooltip>
            <CollapsibleTrigger asChild>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon">
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

export default ChatProConExpandable;
