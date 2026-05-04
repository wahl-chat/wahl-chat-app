'use client';

import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { ConversationInput } from '@/modules/guided-exploration/components/conversation/conversation-input';
import { LeafContent } from '@/modules/guided-exploration/components/exploration-view/leaf-content';
import type {
  Conversation,
  ExplorationNode,
  StreamTargetType,
} from '@/modules/guided-exploration/types';
import { Check, X } from 'lucide-react';
import { useEffect, useRef } from 'react';

interface LeafSidebarProps {
  open: boolean;
  leafNode: ExplorationNode | null;
  conversation: Conversation | null;
  isThinking: boolean;
  thinkingMessage?: string | null;
  isStreaming?: boolean;
  streamBuffer?: string;
  streamingTargetType?: StreamTargetType | null;
  topicSwitchSuggestion?: {
    targetNodeId: string;
    targetNodeName: string;
    message: string;
  } | null;
  suggestedQuestions?: string[];
  /**
   * Hide the "Nach Aspekt" toggle and aspect comparison view (study mode).
   */
  hideAspectView?: boolean;
  /**
   * Render placeholder cards for parties from the active context that have
   * no position on this leaf (study mode).
   */
  showMissingPartiesPlaceholder?: boolean;
  onSendMessage: (message: string) => void;
  onAcceptSwitch?: () => void;
  onDismissSwitch?: () => void;
  /**
   * Called when the user explicitly marks the leaf as done. The parent is
   * responsible for both updating server state and closing the sheet.
   */
  onMarkExplored?: () => void;
  onClose: () => void;
}

/**
 * Right-side `Sheet` that hosts the per-leaf chat — used in v3 instead of
 * a separate exploration page. Reuses {@link LeafContent} (overview +
 * party positions) and {@link ConversationInput}. The streaming/thinking
 * props are already origin-gated by the parent so chat-tab events can't
 * leak in.
 */
export function LeafSidebar({
  open,
  leafNode,
  conversation,
  isThinking,
  thinkingMessage,
  isStreaming,
  streamBuffer,
  streamingTargetType,
  topicSwitchSuggestion,
  suggestedQuestions = [],
  hideAspectView = false,
  showMissingPartiesPlaceholder = false,
  onSendMessage,
  onAcceptSwitch,
  onDismissSwitch,
  onMarkExplored,
  onClose,
}: LeafSidebarProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messageCount = conversation?.messages.length ?? 0;
  const hasAssistantTurn = !!conversation?.messages.some(
    (m) => m.role === 'assistant',
  );
  const isExplored = leafNode?.status === 'explored';
  const showMarkExplored = !!onMarkExplored && !isExplored && hasAssistantTurn;
  const markExploredDisabled = !!isStreaming;

  useEffect(() => {
    if (!open) return;
    if (isThinking || isStreaming) {
      scrollContainerRef.current?.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [open, isThinking, isStreaming, messageCount]);

  const leafName = leafNode?.name ?? null;

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <SheetContent
        side="right"
        className={cn(
          'flex w-full flex-col gap-0 p-0 sm:max-w-xl md:max-w-2xl',
          'data-[state=closed]:duration-200 data-[state=open]:duration-200',
          // Hide the default close (X) baked into SheetContent — we
          // render an explicit one in the header so it sits inline
          // with the other action button.
          '[&>button]:hidden',
        )}
      >
        <SheetHeader className="shrink-0 border-b px-4 py-3 text-left">
          <div className="flex items-center gap-2">
            <SheetTitle className="min-w-0 flex-1 truncate text-base font-medium">
              {leafName ?? 'Thema'}
            </SheetTitle>
            {showMarkExplored && (
              <Button
                type="button"
                size="sm"
                onClick={onMarkExplored}
                disabled={markExploredDisabled}
                className="shrink-0"
              >
                <Check aria-hidden="true" className="mr-1.5 size-4" />
                Als erkundet markieren
              </Button>
            )}
            <SheetClose asChild>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label="Schließen"
                className="size-8 shrink-0"
              >
                <X aria-hidden="true" className="size-4" />
              </Button>
            </SheetClose>
          </div>
          <SheetDescription className="sr-only">
            Mit &ldquo;Als erkundet markieren&ruquo; abschließen.
          </SheetDescription>
        </SheetHeader>

        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-auto"
          tabIndex={-1}
        >
          <div className="mx-auto w-full max-w-2xl px-4 py-6">
            <LeafContent
              conversation={conversation}
              leafName={leafName}
              isThinking={isThinking}
              thinkingMessage={thinkingMessage}
              isStreaming={isStreaming}
              streamBuffer={streamBuffer}
              streamingTargetType={streamingTargetType}
              topicSwitchSuggestion={topicSwitchSuggestion}
              hideAspectView={hideAspectView}
              showMissingPartiesPlaceholder={showMissingPartiesPlaceholder}
              onAcceptSwitch={onAcceptSwitch}
              onDismissSwitch={onDismissSwitch}
            />
          </div>
        </div>

        <div className="flex shrink-0 flex-col gap-2 border-t bg-background px-4 py-3">
          <ConversationInput
            onSubmit={onSendMessage}
            disabled={isThinking}
            placeholder={'Frag mich alles dazu — z.B. „Wer zahlt das?"'}
            suggestedQuestions={suggestedQuestions}
            isLoadingQuestions={
              (isThinking || !!isStreaming) && suggestedQuestions.length === 0
            }
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
