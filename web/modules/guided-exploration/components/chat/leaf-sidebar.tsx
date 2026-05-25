'use client';

import SkipLink from '@/components/skip-link';
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
import { LeafClosurePrompt } from '@/modules/guided-exploration/components/conversation/leaf-closure-prompt';
import { LeafContent } from '@/modules/guided-exploration/components/exploration-view/leaf-content';
import type {
  Conversation,
  ExplorationNode,
  StreamTargetType,
} from '@/modules/guided-exploration/types';
import { Check, X } from 'lucide-react';
import { useCallback, useEffect, useRef } from 'react';

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
   * When true the LLM has judged the leaf substantially explored. The
   * composer is replaced by an accessible closure prompt for as long as
   * this is set.
   */
  showClosurePrompt?: boolean;
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
  /**
   * Called when the user dismisses the closure prompt to keep exploring.
   */
  onContinueExploring?: () => void;
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
  showClosurePrompt = false,
  hideAspectView = false,
  showMissingPartiesPlaceholder = false,
  onSendMessage,
  onAcceptSwitch,
  onDismissSwitch,
  onMarkExplored,
  onContinueExploring,
  onClose,
}: LeafSidebarProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const introRef = useRef<HTMLDivElement>(null);
  const messageCount = conversation?.messages.length ?? 0;
  const hasUserMessage = !!conversation?.messages.some(
    (m) => m.role === 'user',
  );
  const hasAssistantTurn = !!conversation?.messages.some(
    (m) => m.role === 'assistant',
  );
  const isExplored = leafNode?.status === 'explored';
  const showMarkExplored = !!onMarkExplored && !isExplored && hasAssistantTurn;
  const markExploredDisabled = !!isStreaming;

  const leafName = leafNode?.name ?? null;
  const leafId = leafNode?.id ?? null;

  // The most recent assistant turn drives the focus-on-settle move. The summary
  // lives on the `initial_content` message; later answers are followup messages.
  const assistantMessages =
    conversation?.messages.filter((m) => m.role === 'assistant') ?? [];
  const latestAssistant = assistantMessages.at(-1) ?? null;
  const latestAnswerId = latestAssistant?.id ?? null;
  const latestAnswerType = latestAssistant?.type ?? null;

  // Auto-scroll the transcript while a response is being generated.
  useEffect(() => {
    if (!open) return;
    if (isThinking || isStreaming) {
      scrollContainerRef.current?.scrollTo({
        top: scrollContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [open, isThinking, isStreaming, messageCount]);

  // `seenAnswerIdRef` tracks the answer we've already reacted to; reseeding it
  // whenever the active leaf changes means opening a leaf that already has
  // content does NOT move focus — only answers that arrive while this leaf is
  // open do.
  const seenAnswerIdRef = useRef<string | null>(latestAnswerId);
  const prevLeafIdRef = useRef<string | null>(leafId);
  useEffect(() => {
    if (leafId !== prevLeafIdRef.current) {
      prevLeafIdRef.current = leafId;
      seenAnswerIdRef.current = latestAnswerId;
    }
  }, [leafId, latestAnswerId]);

  // Scroll the latest answer into view and move focus onto its heading. The
  // heading is sr-only (position:absolute → its own offsetTop is meaningless),
  // so we measure its in-flow parent as the scroll anchor. Focusing the heading
  // announces "Antwort der KI" — the signal that the user has landed on the
  // answer and can read on — without a competing live-region cue that would
  // interrupt a continuous read before it reaches the party cards.
  const focusLatestAnswer = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const target = container.querySelector<HTMLElement>(
      '[data-leaf-latest-answer]',
    );
    const anchor = target?.parentElement;
    if (target && anchor) {
      const top = anchor.offsetTop - container.offsetTop;
      container.scrollTo({ top: top - 24, behavior: 'smooth' });
      target.focus({ preventScroll: true });
    } else {
      // No answer yet — fall back to the conversation region itself.
      container.focus({ preventScroll: true });
    }
  }, []);

  // When a NEW answer settles while the leaf is open, move focus onto it.
  // Gated to follow-up answers: the initial summary loads right after the sheet
  // opens, where focus is intentionally on the intro — yanking it to the answer
  // mid-read is jarring (the skip-link covers that case instead).
  useEffect(() => {
    if (!open) return;
    if (!latestAnswerId || seenAnswerIdRef.current === latestAnswerId) return;
    seenAnswerIdRef.current = latestAnswerId;

    const isFollowupAnswer =
      latestAnswerType !== null && latestAnswerType !== 'initial_content';
    if (!isFollowupAnswer) return;

    requestAnimationFrame(() => focusLatestAnswer());
  }, [open, latestAnswerId, latestAnswerType, focusLatestAnswer]);

  // "Weiter erkunden": dismissing the closure prompt brings the composer back,
  // so move focus into it — the user just signalled they want to keep asking.
  // A one-shot flag scopes this to the continue action; closing the leaf or
  // switching leaves also clears `showClosurePrompt` but must not grab focus.
  const focusComposerOnReopenRef = useRef(false);
  const prevShowClosurePromptRef = useRef(showClosurePrompt);
  const handleContinueExploring = useCallback(() => {
    focusComposerOnReopenRef.current = true;
    onContinueExploring?.();
  }, [onContinueExploring]);
  useEffect(() => {
    const wasShown = prevShowClosurePromptRef.current;
    prevShowClosurePromptRef.current = showClosurePrompt;
    if (wasShown && !showClosurePrompt && focusComposerOnReopenRef.current) {
      focusComposerOnReopenRef.current = false;
      requestAnimationFrame(() => {
        document.getElementById('leaf-chat-input')?.focus();
      });
    }
  }, [showClosurePrompt]);

  // One narration region for the leaf, for transient process state only. The
  // answer's arrival is conveyed by the focus move onto its heading, not a
  // live-region cue.
  const statusText = isStreaming
    ? 'KI-Antwort wird geschrieben.'
    : isThinking
      ? (thinkingMessage ?? 'Nachricht wird verarbeitet...')
      : '';

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <SheetContent
        side="right"
        // Land focus at the top (the intro), not on a control, so the dialog
        // name + how-it-works description are read first. The skip-link is the
        // next tab stop, letting users jump straight to the conversation.
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          requestAnimationFrame(() => introRef.current?.focus());
        }}
        // Don't let Radix restore focus to the opener card on close — the
        // parent moves focus to its "next topic / chat input" skip-link.
        onCloseAutoFocus={(e) => e.preventDefault()}
        className={cn(
          'flex w-full flex-col gap-0 p-0 sm:max-w-xl md:max-w-2xl',
          'data-[state=closed]:duration-200 data-[state=open]:duration-200',
          // Hide the default close (X) baked into SheetContent — we
          // render an explicit one in the header so it sits inline
          // with the other action button.
          '[&>button]:hidden',
        )}
      >
        {/* Leaf narration: thinking/streaming state, then the arrival cue. */}
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="sr-only"
        >
          {statusText}
        </div>

        {/* Header region: title, how-it-works, jump-to-content, controls. */}
        <SheetHeader className="shrink-0 gap-2 border-b px-4 py-3 text-left">
          <div className="flex items-start gap-2">
            <div
              ref={introRef}
              tabIndex={-1}
              className="min-w-0 flex-1 outline-none"
            >
              <SheetTitle className="truncate text-base font-medium">
                {leafName ?? 'Thema'}
              </SheetTitle>
              {/* sr-only: this guides first-time screen-reader users through
                  the panel's structure. Sighted users get the same from the
                  visible layout, so it would be redundant on screen. */}
              <SheetDescription className="sr-only">
                Detailansicht zum ausgewählten Thema. Oben findest du einen
                Überblick und die Positionen der Parteien. Über das Eingabefeld
                am Ende kannst du eigene Fragen zu diesem Thema stellen; mit der
                Schaltfläche oben rechts schließt du diese Ansicht wieder.
              </SheetDescription>
            </div>
            {/* First tab stop after the intro: jump straight to the latest AI
                answer, past the control buttons. preventDefault + programmatic
                focus avoids a hash change — which, because the sheet is
                position:fixed, would scroll the page (and trip the history-back
                interception, closing the leaf). */}
            <SkipLink
              href="#leaf-content"
              onClick={(e) => {
                e.preventDefault();
                focusLatestAnswer();
              }}
            >
              {hasUserMessage
                ? 'Direkt zur neuesten Antwort der KI springen'
                : 'Zur Themenzusammenfassung der KI springen'}
            </SkipLink>
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
                aria-label="Themen-Detailansicht schließen"
                className="size-8 shrink-0"
              >
                <X aria-hidden="true" className="size-4" />
              </Button>
            </SheetClose>
          </div>
        </SheetHeader>

        {/* Conversation region: the scrollable transcript. */}
        <section
          ref={scrollContainerRef}
          id="leaf-content"
          aria-label="Gesprächsverlauf"
          className="flex-1 overflow-auto outline-none"
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
              latestAnswerId={latestAnswerId}
              showClosurePrompt={showClosurePrompt}
              onAcceptSwitch={onAcceptSwitch}
              onDismissSwitch={onDismissSwitch}
            />
          </div>
        </section>

        {/* Controls region: composer or closure prompt. Both stay mounted and
            we toggle the `hidden` attribute rather than swapping them. The
            closure judgement arrives in the SAME commit as the answer + the
            focus move onto its heading; structurally unmounting a focusable
            region (the composer) in that instant desyncs VoiceOver's cursor
            and strands SR users on the heading. Keeping both mounted means the
            only change near the focused answer is content appended below —
            normal chat behaviour. `hidden` also drops the inactive control
            from the accessibility tree. */}
        <section
          aria-label="Nachricht an die KI"
          className="flex shrink-0 flex-col gap-2 border-t bg-background px-4 py-3"
        >
          <div hidden={!showClosurePrompt}>
            <LeafClosurePrompt
              onClose={onMarkExplored ?? (() => {})}
              onContinue={handleContinueExploring}
              closeDisabled={!onMarkExplored || markExploredDisabled}
              continueDisabled={!onContinueExploring}
            />
          </div>
          <div hidden={showClosurePrompt}>
            <ConversationInput
              inputId="leaf-chat-input"
              onSubmit={onSendMessage}
              disabled={isThinking}
              placeholder={'Frag mich alles dazu — z.B. „Wer zahlt das?"'}
              suggestedQuestions={suggestedQuestions}
              isLoadingQuestions={
                (isThinking || !!isStreaming) && suggestedQuestions.length === 0
              }
              showFirstMessageHint={!hasUserMessage}
            />
          </div>
        </section>
      </SheetContent>
    </Sheet>
  );
}
