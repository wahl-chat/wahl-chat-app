'use client';

import type { AgentMessage } from '@/lib/stores/agent-store';
import { cn } from '@/lib/utils';
import { Bot, User } from 'lucide-react';
import AgentMarkdown from './agent-markdown';

interface Props {
    message: AgentMessage;
    isStreaming?: boolean;
}

export default function AgentChatMessage({ message, isStreaming }: Props) {
    const isUser = message.role === 'user';

    return (
        <article
            className={cn(
                'flex gap-3 md:gap-4',
                isUser ? 'flex-row-reverse' : 'flex-row'
            )}
        >
            {/* Avatar */}
            <div
                className={cn(
                    'flex size-8 shrink-0 items-center justify-center rounded-full md:size-10',
                    isUser
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground'
                )}
            >
                {isUser ? (
                    <User className="size-4 md:size-5" />
                ) : (
                    <Bot className="size-4 md:size-5" />
                )}
            </div>

            {/* Message Content */}
            <div
                className={cn(
                    'flex max-w-[80%] flex-col gap-1',
                    isUser ? 'items-end' : 'items-start'
                )}
            >
                <div
                    className={cn(
                        'rounded-2xl px-4 py-2.5',
                        isUser
                            ? 'rounded-br-md bg-primary text-primary-foreground'
                            : 'rounded-bl-md bg-muted text-foreground'
                    )}
                >
                    {isUser ? (
                        <p className="whitespace-pre-wrap text-sm">{message.content}</p>
                    ) : (
                        <div className="text-sm">
                            <AgentMarkdown content={message.content} />
                            {isStreaming && (
                                <span className="ml-1 inline-block size-2 animate-pulse rounded-full bg-current" />
                            )}
                        </div>
                    )}
                </div>
            </div>
        </article>
    );
}

