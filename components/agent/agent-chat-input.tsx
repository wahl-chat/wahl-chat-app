'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowUp } from 'lucide-react';
import { useCallback, useRef, useEffect, useState } from 'react';
import MessageLoadingBorderTrail from '@/components/chat/message-loading-border-trail';

interface Props {
    onSubmit: (message: string) => void;
}

const CHAT_INPUT_MAX_HEIGHT = 150;
const SINGLE_LINE_THRESHOLD = 50;

export default function AgentChatInput({ onSubmit }: Props) {
    const input = useAgentStore((state) => state.input);
    const setInput = useAgentStore((state) => state.setInput);
    const isStreaming = useAgentStore((state) => state.isStreaming);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const prevInputLengthRef = useRef(0);
    const [isMultiLine, setIsMultiLine] = useState(false);

    const resizeTextarea = useCallback(() => {
        const textarea = textareaRef.current;
        if (!textarea) return;

        const currentHeight = textarea.offsetHeight;
        const isDeleting = input.length < prevInputLengthRef.current;

        if (isDeleting) {
            // When deleting, reset to auto to allow shrinking
            textarea.style.height = 'auto';
            const newHeight = Math.min(textarea.scrollHeight, CHAT_INPUT_MAX_HEIGHT);
            textarea.style.height = `${newHeight}px`;
        } else {
            // When typing, only expand if content exceeds current height
            if (textarea.scrollHeight > currentHeight) {
                const newHeight = Math.min(textarea.scrollHeight, CHAT_INPUT_MAX_HEIGHT);
                textarea.style.height = `${newHeight}px`;
            }
        }

        prevInputLengthRef.current = input.length;
        setIsMultiLine(textarea.scrollHeight > SINGLE_LINE_THRESHOLD);
    }, [input.length]);

    useEffect(() => {
        resizeTextarea();
    }, [input, resizeTextarea]);

    const handleSubmit = useCallback(
        (e: React.FormEvent<HTMLFormElement>) => {
            e.preventDefault();
            if (!input.trim() || isStreaming) return;

            onSubmit(input.trim());
            setInput('');
        },
        [input, isStreaming, onSubmit, setInput]
    );

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setInput(e.target.value);
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (input.trim() && !isStreaming) {
                onSubmit(input.trim());
                setInput('');
            }
        }
    };

    const submitButton = (
        <Button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className={cn(
                'flex size-8 items-center justify-center rounded-full',
                'bg-foreground text-background transition-colors hover:bg-foreground/80',
                'disabled:bg-foreground/20 disabled:text-muted'
            )}
            size="icon"
        >
            <ArrowUp className="size-4 font-bold" />
        </Button>
    );

    return (
        <form
            onSubmit={handleSubmit}
            className={cn(
                'relative w-full overflow-hidden rounded-[24px] border border-input bg-chat-input transition-colors',
                'focus-within:border-zinc-300 dark:focus-within:border-zinc-700'
            )}
        >
            <div className="relative">
                <textarea
                    ref={textareaRef}
                    className={cn(
                        'block w-full resize-none bg-chat-input py-3 pl-4 text-[16px] leading-[1.5] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed',
                        isMultiLine ? 'pr-4' : 'pr-12'
                    )}
                    style={{ maxHeight: CHAT_INPUT_MAX_HEIGHT }}
                    placeholder="Gib hier deine Nachricht ein..."
                    onChange={handleChange}
                    onKeyDown={handleKeyDown}
                    value={input}
                    disabled={isStreaming}
                    maxLength={3000}
                    rows={1}
                />
                {!isMultiLine && (
                    <div className="absolute bottom-2 right-2">
                        {submitButton}
                    </div>
                )}
            </div>

            {isMultiLine && (
                <div className="flex justify-end px-2 pb-2">
                    {submitButton}
                </div>
            )}

            {isStreaming && <MessageLoadingBorderTrail />}
        </form>
    );
}

