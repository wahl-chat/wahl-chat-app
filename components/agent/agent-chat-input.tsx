'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import { useCallback } from 'react';
import MessageLoadingBorderTrail from '@/components/chat/message-loading-border-trail';

interface Props {
    onSubmit: (message: string) => void;
}

export default function AgentChatInput({ onSubmit }: Props) {
    const input = useAgentStore((state) => state.input);
    const setInput = useAgentStore((state) => state.setInput);
    const isStreaming = useAgentStore((state) => state.isStreaming);

    const handleSubmit = useCallback(
        (e: React.FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            if (!input.trim() || isStreaming) return;

            onSubmit(input.trim());
            setInput('');
        },
        [input, isStreaming, onSubmit, setInput]
    );

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setInput(e.target.value);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (input.trim() && !isStreaming) {
                onSubmit(input.trim());
                setInput('');
            }
        }
    };

    return (
        <form
            onSubmit={handleSubmit}
            className={cn(
                'relative w-full overflow-hidden rounded-[30px] border border-input bg-chat-input transition-colors',
                'focus-within:border-zinc-300 dark:focus-within:border-zinc-700'
            )}
        >
            {isStreaming && <MessageLoadingBorderTrail />}

            <input
                className="w-full bg-chat-input py-3 pl-4 pr-12 text-[16px] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed"
                placeholder="Gib hier deine Nachricht ein..."
                onChange={handleChange}
                onKeyDown={handleKeyDown}
                value={input}
                disabled={isStreaming}
                maxLength={2000}
            />
            <Button
                type="submit"
                disabled={!input.trim() || isStreaming}
                className={cn(
                    'absolute right-2 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-full',
                    'bg-foreground text-background transition-colors hover:bg-foreground/80',
                    'disabled:bg-foreground/20 disabled:text-muted'
                )}
                size="icon"
            >
                <ArrowUp className="size-4 font-bold" />
            </Button>
        </form>
    );
}

