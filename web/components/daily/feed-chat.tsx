'use client';

import StickyInput from '@/components/sticky-input';
import {
  type FeedChatMode,
  type ItemChat,
  type ReturnChat,
  chatAbout,
  chatSessionHref,
  clearReturnChat,
  feedChatHref,
  itemChatHref,
  itemProcedureIds,
  latestGeneralChat,
  markFromFeed,
  readReturnChat,
  storedItemId,
} from '@/lib/daily/chat-handoff';
import { type DetailItem, itemTitle } from '@/lib/daily/items';
import type { ChatPreset, Context } from '@/lib/firebase/firebase.types';
import { useChatHistory } from '@/lib/hooks/use-chat-history';
import type { PartyDetails } from '@/lib/party-details';
import { cn } from '@/lib/utils';
import { ArrowRightIcon, MessageCircleIcon, PlusIcon } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

export type FeedChatRequest =
  | { question: string; item?: DetailItem; preset?: ChatPreset }
  | { sessionId: string; label?: string }
  /** An empty chat about the item, opening with its suggested questions. */
  | { newChatAbout: DetailItem };

/** What the sheet variant needs to run the general chat over the feed. */
export type FeedChatContext = {
  context: Context;
  contexts: Context[];
  parties?: PartyDetails[];
};

type Parked = {
  label: string;
  /** The feed item the chat stepped aside for; asking about it continues
   * the chat. */
  itemId: string | null;
  open: () => void;
};

type FeedChat = {
  ask: (request: FeedChatRequest) => void;
  /** The user's last active chat about the item or its procedures. */
  chatFor: (item: DetailItem) => ItemChat | null;
  /** The user's latest chat about no item. */
  general: ItemChat | null;
  /** A chat the reader stepped away from: tucked away in the sheet, or the
   * chat page they left for the feed. */
  parked: Parked | null;
};

const FeedChatApi = createContext<FeedChat | null>(null);

// The chat loads with the first question, not with the feed.
const FeedChatSheet = dynamic(() => import('./feed-chat-sheet'), {
  ssr: false,
});

function chatPageHref(request: FeedChatRequest): string {
  if ('sessionId' in request) return chatSessionHref(request.sessionId);
  if ('newChatAbout' in request) return itemChatHref(request.newChatAbout);
  return feedChatHref(request.item, request.question, request.preset);
}

function openChatPage(
  router: ReturnType<typeof useRouter>,
  request: FeedChatRequest,
  fromItemId: string | null,
) {
  clearReturnChat();
  markFromFeed(fromItemId);
  router.push(chatPageHref(request));
}

/** Asking from the feed: on the chat page, or in the sheet where the feed
 * provides one. */
export function useFeedChat(): FeedChat {
  const api = useContext(FeedChatApi);
  if (!api) throw new Error('useFeedChat needs a FeedChatProvider');
  return api;
}

export type Sheet = {
  /** One chat store per conversation. */
  key: string;
  request: FeedChatRequest;
  label: string;
  open: boolean;
  /** The item view the sheet covers and leaving it shows again, if any. */
  returnTo: ItemNoun | null;
  parkedFor: string | null;
  /** Reported by the running chat. */
  sessionId: string | null;
  busy: boolean;
  /** A question for the running chat; with an item, about that item. */
  followUp: { seq: number; question: string; itemId?: string } | null;
};

type ProviderProps = {
  children: ReactNode;
  mode: FeedChatMode;
  chatContext?: FeedChatContext;
  /** Shows a feed item's detail view; false when the feed has not loaded it. */
  openItem: (feedItemId: string) => boolean;
  /** Hides the open detail view while the sheet is up; it is modal. */
  closeItem: () => void;
  /** The item whose detail view is open, if any. */
  openItemId: string | null;
  openItemNoun: ItemNoun | null;
};

// Marks the history entry the open sheet adds, so Back tucks it away.
const SHEET_STATE = 'feedChatSheet';

export function isSheetEntry(state: unknown): boolean {
  return Boolean(
    state && typeof state === 'object' && SHEET_STATE in (state as object),
  );
}

export type ItemNoun = 'Abstimmung' | 'Debatte';

function newSheet(
  key: string,
  request: FeedChatRequest,
  label: string,
  returnTo: ItemNoun | null,
): Sheet {
  return {
    key,
    request,
    label,
    open: true,
    returnTo,
    parkedFor: null,
    sessionId: 'sessionId' in request ? request.sessionId : null,
    busy: false,
    followUp: null,
  };
}

export function FeedChatProvider({
  children,
  mode,
  chatContext,
  openItem,
  closeItem,
  openItemId,
  openItemNoun,
}: ProviderProps) {
  const router = useRouter();
  const history = useChatHistory();
  const chatFor = useCallback(
    (item: DetailItem) =>
      chatAbout(history, storedItemId(item), itemProcedureIds(item)),
    [history],
  );
  const general = useMemo(() => latestGeneralChat(history), [history]);
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const seq = useRef(0);
  const inSheet = mode === 'sheet' && chatContext !== undefined;
  // The feed's callbacks change every render; read them through refs so
  // the chat's context stays stable.
  const feed = useRef({ openItem, closeItem, openItemId, openItemNoun });
  feed.current = { openItem, closeItem, openItemId, openItemNoun };
  const current = useRef(sheet);
  current.current = sheet;
  const pushed = useRef(false);

  const open = sheet?.open ?? false;
  useEffect(() => {
    if (open && !pushed.current) {
      window.history.pushState(
        { ...window.history.state, [SHEET_STATE]: true },
        '',
      );
      pushed.current = true;
    }
  }, [open]);

  useEffect(() => {
    const onPop = (event: PopStateEvent) => {
      const onSheetEntry = isSheetEntry(event.state);
      pushed.current = onSheetEntry && current.current !== null;
      setSheet((value) =>
        value && value.open !== onSheetEntry
          ? {
              ...value,
              open: onSheetEntry,
              parkedFor: onSheetEntry ? null : value.parkedFor,
            }
          : value,
      );
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const minimize = useCallback(() => {
    setSheet((value) => (value ? { ...value, open: false } : value));
    if (pushed.current) {
      pushed.current = false;
      window.history.back();
    }
  }, []);

  const end = useCallback(() => {
    // Unmarked, Forward onto this entry later shows the feed, not a sheet
    // that is gone.
    if (pushed.current) {
      const { [SHEET_STATE]: _, ...state } = window.history.state ?? {};
      window.history.replaceState(state, '');
    }
    minimize();
    setSheet(null);
  }, [minimize]);

  const ask = useCallback(
    (request: FeedChatRequest) => {
      if (!inSheet) {
        openChatPage(router, request, feed.current.openItemId);
        return;
      }
      // Read before the item view is hidden: leaving the sheet shows it.
      const returnTo = feed.current.openItemNoun;
      feed.current.closeItem();
      seq.current += 1;
      const id = seq.current;
      setSheet((value) => {
        if ('sessionId' in request) {
          if (
            value &&
            (value.sessionId === request.sessionId ||
              value.key === `session:${request.sessionId}`)
          ) {
            return { ...value, open: true, returnTo };
          }
          return newSheet(
            `session:${request.sessionId}`,
            request,
            request.label ?? 'Dein Chat',
            returnTo,
          );
        }
        if ('newChatAbout' in request) {
          return newSheet(
            `new:${id}`,
            request,
            itemTitle(request.newChatAbout),
            returnTo,
          );
        }
        const itemId = request.item ? storedItemId(request.item) : undefined;
        // A running answer or the item the chat stepped aside for: the
        // question continues that chat instead of dropping it.
        if (value && (value.busy || (itemId && value.parkedFor === itemId))) {
          return {
            ...value,
            open: true,
            returnTo,
            parkedFor: null,
            followUp: { seq: id, question: request.question, itemId },
          };
        }
        return newSheet(`ask:${id}`, request, request.question, returnTo);
      });
    },
    [inSheet, router],
  );

  const openFeedItem = useCallback((feedItemId: string) => {
    // The sheet's history entry stays, so Back from the item returns here.
    pushed.current = false;
    if (!feed.current.openItem(feedItemId)) {
      pushed.current = true;
      return false;
    }
    // The item's entry copies the sheet's state; unmarked, Back onto it
    // leaves the chat tucked away.
    const { [SHEET_STATE]: _, ...state } = window.history.state ?? {};
    window.history.replaceState(state, '');
    setSheet((value) =>
      value ? { ...value, open: false, parkedFor: feedItemId } : value,
    );
    return true;
  }, []);

  const report = useCallback((sessionId: string | null, busy: boolean) => {
    setSheet((value) =>
      value && (value.sessionId !== sessionId || value.busy !== busy)
        ? { ...value, sessionId: sessionId ?? value.sessionId, busy }
        : value,
    );
  }, []);

  // The chat page variant: the chat the reader left for the feed.
  const [returnChat, setReturnChat] = useState<ReturnChat | null>(null);
  useEffect(() => {
    if (!inSheet) setReturnChat(readReturnChat());
  }, [inSheet]);
  // Back on the feed, the detour from the chat is over; the item opened
  // again later is a fresh visit.
  const itemOpen = openItemId !== null;
  const wasOpen = useRef(itemOpen);
  useEffect(() => {
    if (wasOpen.current && !itemOpen && returnChat) {
      clearReturnChat();
      setReturnChat(null);
    }
    wasOpen.current = itemOpen;
  }, [itemOpen, returnChat]);

  const label = sheet?.label;
  const parkedFor = sheet?.parkedFor ?? null;
  const parked = useMemo<Parked | null>(
    () =>
      returnChat
        ? {
            label: returnChat.label,
            itemId: returnChat.itemId,
            open: () =>
              openChatPage(
                router,
                { sessionId: returnChat.sessionId },
                feed.current.openItemId,
              ),
          }
        : label !== undefined && !open
          ? {
              label,
              itemId: parkedFor,
              open: () => {
                // The item was opened from the chat, one step above it in
                // history: going back keeps Zum Feed and Back from looping.
                if (parkedFor) {
                  window.history.back();
                  return;
                }
                const returnTo = feed.current.openItemNoun;
                feed.current.closeItem();
                setSheet((value) =>
                  value ? { ...value, open: true, returnTo } : value,
                );
              },
            }
          : null,
    [returnChat, router, label, open, parkedFor],
  );

  const api = useMemo(
    () => ({ ask, chatFor, general, parked }),
    [ask, chatFor, general, parked],
  );

  return (
    <FeedChatApi.Provider value={api}>
      {children}
      {inSheet && sheet && chatContext && (
        <FeedChatSheet
          key={sheet.key}
          sheet={sheet}
          chatContext={chatContext}
          openFeedItem={openFeedItem}
          onMinimize={minimize}
          onClose={end}
          onReport={report}
        />
      )}
    </FeedChatApi.Provider>
  );
}

/** A chat's name in its resume buttons. */
function chatName(title: string | undefined): string {
  return title?.trim() || 'Weitermachen';
}

/** Back into a saved chat, labelled by its title or `fallback`. */
function resume(chat: ItemChat, fallback: string): FeedChatRequest {
  return { sessionId: chat.sessionId, label: chat.title || fallback };
}

/** "Dein Chat: <title> →" as a translucent bubble, narrower than the
 * input under it, so it reads as a hint above it, not a second bar. */
function ChatBubble({
  title,
  onClick,
  className,
}: {
  title: string | undefined;
  onClick: () => void;
  className?: string;
}) {
  const name = chatName(title);
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Dein Chat: ${name}`}
      className={cn(
        'mx-auto flex min-h-10 w-[80%] min-w-0 items-center justify-center gap-1.5 rounded-full border border-[var(--daily-border)] bg-[var(--daily-canvas)]/70 px-3 text-[13px] text-[var(--daily-muted)] shadow-sm backdrop-blur-md transition-colors hover:text-[var(--daily-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--daily-ink)]',
        className,
      )}
    >
      <MessageCircleIcon className="size-4 shrink-0" aria-hidden />
      <span className="truncate">
        Dein Chat:{' '}
        <span className="font-medium text-[var(--daily-ink)]">{name}</span>
      </span>
      <ArrowRightIcon className="size-4 shrink-0" aria-hidden />
    </button>
  );
}

function useItemChatSlot(item: DetailItem) {
  const { chatFor, parked } = useFeedChat();
  const itemId = storedItemId(item);
  const cameFrom = parked && itemId && parked.itemId === itemId ? parked : null;
  return { cameFrom, chat: cameFrom ? null : chatFor(item) };
}

/** Room at the end of the item for its floating chat button, so the last
 * lines can scroll clear of it. */
export function ItemChatSlotSpace({ item }: { item: DetailItem }) {
  const { cameFrom, chat } = useItemChatSlot(item);
  return cameFrom || chat ? <div aria-hidden className="h-14" /> : null;
}

/** The one floating hint above an item's ask bar: back to the chat the
 * item was opened from, else the reader's own chat about it. A new chat
 * starts in the ask bar itself. */
export function ItemChatSlot({ item }: { item: DetailItem }) {
  const { ask } = useFeedChat();
  const { cameFrom, chat } = useItemChatSlot(item);
  if (!cameFrom && !chat) return null;
  return (
    <div className="pointer-events-none absolute inset-x-0 -top-14 z-10 flex justify-center px-4 [&>*]:pointer-events-auto">
      {cameFrom ? (
        <button
          type="button"
          onClick={cameFrom.open}
          title={cameFrom.label}
          className="flex min-h-10 max-w-full items-center gap-1.5 rounded-full bg-[var(--daily-ink)] px-4 text-[14px] font-semibold text-[var(--daily-canvas)] shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--daily-ink)] focus-visible:ring-offset-2"
        >
          <MessageCircleIcon className="size-4 shrink-0" aria-hidden />
          <span className="truncate">Zurück zum Chat</span>
          <ArrowRightIcon className="size-4 shrink-0" aria-hidden />
        </button>
      ) : (
        chat && (
          <ChatBubble
            title={chat.title}
            onClick={() => ask(resume(chat, itemTitle(item)))}
          />
        )
      )}
    </div>
  );
}

/** The feed's ask bar: a question on its own, not about the card in view;
 * matching feed items come with the answer. */
export function FeedAskBar({ className }: { className?: string }) {
  const { ask, general } = useFeedChat();
  return (
    <div className={className}>
      {general && (
        <ChatBubble
          title={general.title}
          onClick={() => ask(resume(general, 'Dein Chat'))}
          className="mb-1.5"
        />
      )}
      <StickyInput
        isLoading={false}
        clearOnSubmit
        onSubmit={(question) => {
          if (question.trim()) ask({ question });
        }}
        placeholder="Frag zur Politik im Bundestag …"
        className="relative mx-2 pb-3 md:pb-3"
      />
    </div>
  );
}

/** A card's way into its chats: the reader's last one and a new one, as
 * one compact button group. */
export function ChatButtons({
  item,
  className,
}: {
  item: DetailItem;
  className?: string;
}) {
  const { ask, chatFor } = useFeedChat();
  const chat = chatFor(item);
  if (!chat) return null;
  const segment =
    'flex min-h-10 items-center gap-1.5 transition-colors hover:bg-[var(--daily-border)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--daily-ink)]';
  return (
    <div
      className={cn(
        'flex min-w-0 max-w-full overflow-hidden rounded-full border border-[var(--daily-border)] bg-[var(--daily-surface)] text-[14px]',
        className,
      )}
    >
      <button
        type="button"
        onClick={() => ask(resume(chat, itemTitle(item)))}
        title={chat.title}
        aria-label={`Dein Chat dazu${chat.title ? `: ${chat.title}` : ''}`}
        className={cn(segment, 'min-w-0 pl-3.5 pr-3')}
      >
        <MessageCircleIcon className="size-4 shrink-0" aria-hidden />
        <span className="truncate">
          <span className="text-[var(--daily-muted)]">Dein Chat:</span>{' '}
          <span className="font-semibold">{chatName(chat.title)}</span>
        </span>
      </button>
      <span aria-hidden className="w-px shrink-0 bg-[var(--daily-border)]" />
      <button
        type="button"
        onClick={() => ask({ newChatAbout: item })}
        aria-label="Neuer Chat zu diesem Beitrag"
        title="Neuer Chat"
        className={cn(segment, 'shrink-0 px-3')}
      >
        <PlusIcon className="size-4" aria-hidden />
      </button>
    </div>
  );
}
