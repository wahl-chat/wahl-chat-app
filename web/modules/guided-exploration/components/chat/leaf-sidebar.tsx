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
import { LeafContent } from '@/modules/guided-exploration/components/exploration-view/leaf-content';
import type {
  Conversation,
  ExplorationNode,
  StreamTargetType,
} from '@/modules/guided-exploration/types';
import { Check, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Cue spoken once an answer finishes. The answer's <h2> heading carries its
 * content, so this only flags completion and points at the heading rotor — no
 * focus steal.
 */
const FINISHED_ANNOUNCEMENT =
  'Antwort fertig. Über das Überschriften-Menü dorthin navigieren.';

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
   * When true the LLM has judged the leaf substantially explored. An accessible
   * closure prompt is rendered inline at the end of the transcript (the composer
   * stays mounted) for as long as this is set.
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

  // Single polite narration for the leaf: thinking → writing → finished. One
  // stable region whose text we mutate (no keyed remount — VoiceOver reliably
  // announces a text change on a stable node, but often misses a full child
  // swap). One region also avoids two polite regions changing at once on
  // completion, where the screen reader tends to service only one.
  const [liveText, setLiveText] = useState('');
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

  // Scroll the latest answer to the top of the transcript. The heading is
  // sr-only (position:absolute → its own offsetTop is meaningless), so we
  // measure its in-flow parent as the scroll anchor.
  const scrollLatestAnswerIntoView = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const target = container.querySelector<HTMLElement>(
      '[data-leaf-latest-answer]',
    );
    const anchor = target?.parentElement;
    if (target && anchor) {
      const top = anchor.offsetTop - container.offsetTop;
      container.scrollTo({ top: top - 24, behavior: 'smooth' });
    }
  }, []);

  // The user-initiated skip-link ("zur neuesten Antwort springen") scrolls AND
  // moves focus onto the answer's heading — that move is requested, not
  // imposed. Falls back to the conversation region when there's no answer yet.
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
      container.focus({ preventScroll: true });
    }
  }, []);

  // When a NEW answer settles while the leaf is open, announce completion and
  // scroll it into view — but don't move focus. Gated to follow-up answers: the
  // initial summary loads right after the sheet opens, where focus is
  // intentionally on the intro (the skip-link covers jumping to it).
  useEffect(() => {
    if (!open) return;
    if (!latestAnswerId || seenAnswerIdRef.current === latestAnswerId) return;
    seenAnswerIdRef.current = latestAnswerId;

    const isFollowupAnswer =
      latestAnswerType !== null && latestAnswerType !== 'initial_content';
    if (!isFollowupAnswer) return;

    // Distinct from the "wird geschrieben" text it replaces, so the change is
    // detected and spoken.
    setLiveText(FINISHED_ANNOUNCEMENT);
    requestAnimationFrame(() => scrollLatestAnswerIntoView());
    // Drop the text once spoken so it isn't left sitting in the region (which
    // a screen reader can re-read on restart). Functional guard so it never
    // clobbers the next turn's "wird verarbeitet" if that has already landed.
    const clear = window.setTimeout(
      () => setLiveText((cur) => (cur === FINISHED_ANNOUNCEMENT ? '' : cur)),
      4000,
    );
    return () => clearTimeout(clear);
  }, [open, latestAnswerId, latestAnswerType, scrollLatestAnswerIntoView]);

  // "Weiter erkunden": dismissing the inline closure prompt unmounts the focused
  // button, so move focus into the composer — the user just signalled they want
  // to keep asking. A one-shot flag scopes this to the continue action; closing
  // the leaf or switching leaves also clears `showClosurePrompt` but must not
  // grab focus.
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
    } else if (!wasShown && showClosurePrompt) {
      // The prompt now appears inline at the end of the transcript; bring it
      // into view. Scroll only — no focus move, so the SR cursor and whatever
      // the user has focused (often the composer) stay put.
      requestAnimationFrame(() => {
        document
          .getElementById('leaf-closure-heading')
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }
  }, [showClosurePrompt]);

  // Narrate transient process state into the same region. Crucially we do NOT
  // clear when idle: the finished cue (set by the answer-settled effect above)
  // must survive the moment streaming stops, so neither-branch is a no-op.
  useEffect(() => {
    if (isStreaming) {
      setLiveText('KI-Antwort wird geschrieben.');
    } else if (isThinking) {
      setLiveText(thinkingMessage ?? 'Nachricht wird verarbeitet...');
    }
  }, [isThinking, isStreaming, thinkingMessage]);

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
        {/* The leaf's single narration region: thinking → writing → finished.
            One stable node whose text we mutate, so each transition is a real
            content change VoiceOver announces — and there's never a second
            polite region changing at the same instant to compete with it. */}
        <div
          role="status"
          aria-live="polite"
          aria-atomic="true"
          className="sr-only"
        >
          {liveText}
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

        {/* One landmark groups the transcript and the composer so a screen
            reader flips between them without an extra nested-region stop. */}
        <section
          aria-label="Gespräch zu diesem Thema"
          className="flex min-h-0 flex-1 flex-col"
        >
          {/* The scrollable transcript. Keeps id + tabIndex so the header's
              "zur neuesten Antwort springen" skip-link can target it. */}
          <div
            ref={scrollContainerRef}
            id="leaf-content"
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
                onMarkExplored={onMarkExplored}
                onContinueExploring={handleContinueExploring}
                markExploredDisabled={markExploredDisabled}
                onAcceptSwitch={onAcceptSwitch}
                onDismissSwitch={onDismissSwitch}
              />
            </div>
          </div>

          {/* The composer stays mounted and visible at all times — even while
              the closure prompt is shown (the prompt now lives inline at the end
              of the transcript). Never hiding the focused textarea is what keeps
              VoiceOver from dropping focus to <body> when the closure judgement
              arrives. The composer is never disabled either. */}
          <div className="flex shrink-0 flex-col gap-2 border-t bg-background px-4 py-3">
            <ConversationInput
              inputId="leaf-chat-input"
              onSubmit={onSendMessage}
              placeholder="Frag mich alles dazu"
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
