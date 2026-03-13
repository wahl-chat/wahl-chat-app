'use client';

import CopyButton from '@/components/chat/copy-button';
import type { AgentMessage } from '@/lib/stores/agent-store';
import AgentMarkdown from './agent-chat-markdown';
import AgentSourcesButton from './agent-sources-button';

interface Props {
  message: AgentMessage;
  isStreaming?: boolean;
}

export default function AgentChatMessage({ message, isStreaming }: Props) {
  const isUser = message.role === 'user';
  const hasSources = message.sources && message.sources.length > 0;

  if (isUser) {
    return (
      <article className="flex flex-col items-end justify-end gap-1">
        <div className="w-fit max-w-[90%] rounded-[20px] bg-muted px-4 py-2 text-foreground whitespace-pre-wrap">
          {message.content}
        </div>
      </article>
    );
  }

  return (
    <article className="flex flex-col gap-2">
      <div className="flex flex-col gap-2">
        <div className="flex flex-col gap-4 [&_li]:leading-[1.75] [&_p]:leading-[1.75]">
          <AgentMarkdown content={message.content} sources={message.sources} />
          {isStreaming && (
            <span className="inline-block size-2 animate-pulse rounded-full bg-current" />
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-muted-foreground">
          {hasSources && message.sources && (
            <AgentSourcesButton
              sources={message.sources}
              messageContent={message.content}
            />
          )}
          <CopyButton
            text={message.content}
            variant="ghost"
            size="icon"
            className="size-8"
          />
        </div>
      </div>
    </article>
  );
}
