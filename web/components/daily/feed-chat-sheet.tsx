'use client';

import AnonymousUserChatStoreUpdater from '@/components/auth/anonymous-user-chat-store-updater';
import ChatAnchorCard from '@/components/chat/chat-anchor-card';
import ChatDynamicChatInput from '@/components/chat/chat-dynamic-chat-input';
import { ChatHostProvider } from '@/components/chat/chat-host';
import {
  ChatJumpBackPill,
  ChatJumpProvider,
} from '@/components/chat/chat-jump';
import ChatMessagesView from '@/components/chat/chat-messages-view';
import {
  ChatStoreProvider,
  useChatStore,
} from '@/components/providers/chat-store-provider';
import { ContextProvider } from '@/components/providers/context-provider';
import SseChatProvider from '@/components/providers/sse-chat-provider';
import type { FeedPick } from '@/lib/chat-feed';
import { GENERAL_CONTEXT_ID } from '@/lib/constants';
import { storedItemId } from '@/lib/daily/chat-handoff';
import { getChatFeedPicks } from '@/lib/server-actions/chat-feed-picks';
import { cn } from '@/lib/utils';
import { ChevronDownIcon, XIcon } from 'lucide-react';
import {
  type KeyboardEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { FeedChatContext, Sheet } from './feed-chat';

type SheetProps = {
  sheet: Sheet;
  chatContext: FeedChatContext;
  openFeedItem: (feedItemId: string) => boolean;
  onMinimize: () => void;
  onClose: () => void;
  /** The chat's session and whether an answer is still coming. */
  onReport: (sessionId: string | null, busy: boolean) => void;
};

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

/** Keeps Tab inside the sheet. */
function trapTab(event: KeyboardEvent<HTMLElement>) {
  const items = [
    ...event.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE),
  ].filter((element) => element.offsetParent !== null);
  const first = items[0];
  const last = items.at(-1);
  if (!first || !last) return;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

/** The general chat in a sheet over the feed. It stays mounted while
 * tucked away, so a running answer keeps streaming. */
export default function FeedChatSheet({
  sheet,
  chatContext,
  openFeedItem,
  onMinimize,
  onClose,
  onReport,
}: SheetProps) {
  const { request, open } = sheet;
  const host = useMemo(
    () => ({ mode: 'sheet' as const, openFeedItem }),
    [openFeedItem],
  );
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const root = document.documentElement;
    const previous = root.style.overflow;
    root.style.overflow = 'hidden';
    const returnTo =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    panel.current?.focus({ preventScroll: true });
    // Fixed boxes keep the full screen's size when a phone keyboard opens,
    // so the feed would show between the input and the keyboard; the sheet
    // follows the part of the screen still visible instead.
    const viewport = window.visualViewport;
    const fit = () => {
      const node = panel.current;
      if (!node || !viewport) return;
      const gap = viewport.height * 0.05;
      node.style.top = `${viewport.offsetTop + gap}px`;
      node.style.height = `${viewport.height - gap}px`;
      node.style.bottom = 'auto';
    };
    fit();
    viewport?.addEventListener('resize', fit);
    viewport?.addEventListener('scroll', fit);
    return () => {
      viewport?.removeEventListener('resize', fit);
      viewport?.removeEventListener('scroll', fit);
      for (const key of ['top', 'height', 'bottom'] as const) {
        panel.current?.style.removeProperty(key);
      }
      root.style.overflow = previous;
      if (returnTo?.isConnected && !returnTo.closest('[inert]')) {
        returnTo.focus({ preventScroll: true });
      }
    };
  }, [open]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    // A preview or menu inside the chat handles its own Escape first.
    if (event.key === 'Escape' && !event.nativeEvent.defaultPrevented) {
      onMinimize();
    } else if (event.key === 'Tab') {
      trapTab(event);
    }
  };

  const item =
    'newChatAbout' in request
      ? request.newChatAbout
      : 'question' in request
        ? request.item
        : undefined;
  const itemId = item ? storedItemId(item) : undefined;
  // An empty chat opens with the item's questions, drawn from the feed.
  const [picks, setPicks] = useState<FeedPick[] | undefined>(undefined);
  const empty = 'newChatAbout' in request;
  useEffect(() => {
    if (!empty) return;
    let cancelled = false;
    getChatFeedPicks()
      .then((found) => {
        if (!cancelled) setPicks(found);
      })
      .catch(() => {
        if (!cancelled) setPicks([]);
      });
    return () => {
      cancelled = true;
    };
  }, [empty]);

  return (
    <ContextProvider
      context={chatContext.context}
      contexts={chatContext.contexts}
      parties={chatContext.parties}
    >
      <ChatStoreProvider contextId={GENERAL_CONTEXT_ID}>
        <AnonymousUserChatStoreUpdater />
        <SseChatProvider>
          <ChatHostProvider value={host}>
            <ChatJumpProvider>
              <FollowUp followUp={sheet.followUp} />
              <Report onReport={onReport} />
              {open && (
                // biome-ignore lint/a11y/useKeyWithClickEvents: pointer only; keyboard users close with Escape or the sheet's buttons
                <div
                  aria-hidden
                  onClick={onMinimize}
                  className="fixed inset-0 z-40 bg-black/40"
                />
              )}
              {/* Below Radix overlays (z-50), so previews and menus opened
                  from the chat show above it. */}
              <div
                ref={panel}
                role="dialog"
                aria-modal={open}
                aria-label="Chat"
                tabIndex={-1}
                inert={!open}
                onKeyDown={onKeyDown}
                className={cn(
                  'fixed inset-x-0 bottom-0 top-[5dvh] z-40 mx-auto flex max-w-2xl flex-col overflow-hidden rounded-t-2xl bg-background outline-none transition-transform duration-300 ease-out motion-reduce:transition-none',
                  open ? 'translate-y-0 shadow-2xl' : 'translate-y-full',
                )}
              >
                <div className="flex items-center justify-between gap-2 px-2 pt-1.5">
                  <button
                    type="button"
                    onClick={onMinimize}
                    className="flex min-h-11 items-center gap-1 rounded-md px-2 text-sm font-medium hover:bg-muted"
                  >
                    <ChevronDownIcon className="size-4" aria-hidden />
                    Zum Feed
                  </button>
                  <span
                    aria-hidden
                    className="h-1.5 w-10 rounded-full bg-muted-foreground/30"
                  />
                  <button
                    type="button"
                    aria-label="Chat schließen"
                    onClick={onClose}
                    className="flex size-11 items-center justify-center rounded-md hover:bg-muted"
                  >
                    <XIcon className="size-5" aria-hidden />
                  </button>
                </div>
                <ChatAnchorCard />
                <ChatMessagesView
                  sessionId={
                    'sessionId' in request ? request.sessionId : undefined
                  }
                  initialQuestion={
                    'question' in request ? request.question : undefined
                  }
                  anchor={itemId ? { feed_item_id: itemId } : undefined}
                  feedPicks={empty ? (picks ?? []) : undefined}
                  preset={
                    'question' in request && itemId ? request.preset : undefined
                  }
                />
                <div className="relative px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:px-4">
                  <div className="pointer-events-none absolute inset-x-0 -top-14 z-10 flex justify-center">
                    <ChatJumpBackPill />
                  </div>
                  <ChatDynamicChatInput
                    initialSystemStatus={{ is_at_rate_limit: false }}
                  />
                </div>
              </div>
            </ChatJumpProvider>
          </ChatHostProvider>
        </SseChatProvider>
      </ChatStoreProvider>
    </ContextProvider>
  );
}

/** Sends a question to the running chat once it is free, with the item as
 * its subject when there is one. */
function FollowUp({ followUp }: { followUp: Sheet['followUp'] }) {
  const setAnchor = useChatStore((state) => state.setAnchor);
  const addUserMessage = useChatStore((state) => state.addUserMessage);
  const userId = useChatStore((state) => state.userId);
  const busy = useChatStore((state) => state.loading.newMessage);
  const sent = useRef(0);

  useEffect(() => {
    if (!followUp || !userId || busy || sent.current === followUp.seq) return;
    sent.current = followUp.seq;
    if (followUp.itemId) setAnchor({ feed_item_id: followUp.itemId });
    addUserMessage(userId, followUp.question);
  }, [followUp, userId, busy, setAnchor, addUserMessage]);

  return null;
}

/** Tells the feed which session the sheet holds and whether it is busy. */
function Report({
  onReport,
}: { onReport: (sessionId: string | null, busy: boolean) => void }) {
  const sessionId = useChatStore((state) => state.chatSessionId ?? null);
  const busy = useChatStore((state) => state.loading.newMessage);
  useEffect(() => onReport(sessionId, busy), [onReport, sessionId, busy]);
  return null;
}
