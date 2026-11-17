'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { useTenant } from '@/components/providers/tenant-provider';
import type { FeedPick } from '@/lib/chat-feed';
import type {
  ChatAnchor,
  ChatSession,
  ProposedQuestion,
} from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import type { GroupedMessage } from '@/lib/stores/chat-store.types';
import { useEffect, useMemo, useRef } from 'react';
import ChatEmptyView from './chat-empty-view';
import ChatGroupedMessages from './chat-grouped-messages';
import ChatMessagesScrollView from './chat-messages-scroll-view';
import { INITIAL_MESSAGE_ID } from './chat-single-user-message';
import CurrentStreamingMessages from './current-streaming-messages';
import GeneralChatEmptyView from './general-chat-empty-view';

type Props = {
  sessionId?: string;
  chatSession?: ChatSession;
  messages?: GroupedMessage[];
  parties?: PartyDetails[];
  allParties?: PartyDetails[];
  proposedQuestions?: ProposedQuestion[];
  /** General chat only: the feed its empty state draws questions from. */
  feedPicks?: FeedPick[];
  initialQuestion?: string;
  prefilledQuestion?: string;
  anchor?: ChatAnchor;
};

function ChatMessagesView({
  sessionId,
  chatSession,
  messages,
  parties,
  allParties,
  proposedQuestions,
  feedPicks,
  initialQuestion,
  prefilledQuestion,
  anchor,
}: Props) {
  const hasFetched = useRef(false);
  // Server props arrive as new objects on every RSC render; keyed by value so a
  // re-render mid-stream does not re-hydrate and reset the session.
  const anchorKey = anchor ? JSON.stringify(anchor) : '';
  const anchorRef = useRef(anchor);
  anchorRef.current = anchor;
  const storeMessages = useChatStore((state) => state.messages);
  const hydrateChatSession = useChatStore((state) => state.hydrateChatSession);
  const { user } = useAnonymousAuth();
  const tenant = useTenant();

  const hasCurrentStreamingMessages = useChatStore(
    (state) => state.currentStreamingMessages !== undefined,
  );

  const lastHydration = useRef<unknown[]>([]);

  useEffect(() => {
    if (!user?.uid) return;
    // A re-run with the same inputs (React's dev double-invoke) would treat the
    // session this page just started as a page change and drop its stream.
    const inputs = [
      sessionId,
      user.uid,
      chatSession,
      hydrateChatSession,
      messages,
      parties,
      initialQuestion,
      prefilledQuestion,
      tenant,
      anchorKey,
    ];
    if (inputs.every((value, i) => value === lastHydration.current[i])) return;
    lastHydration.current = inputs;

    hydrateChatSession({
      chatSession,
      chatSessionId: sessionId,
      messages,
      preSelectedPartyIds: parties?.map((party) => party.party_id),
      // Only auto-send the initial question the first time this component hydrates
      initialQuestion: hasFetched.current ? undefined : initialQuestion,
      // Same guard: re-prefilling on a later hydration would overwrite whatever
      // the user has since typed.
      prefilledQuestion: hasFetched.current ? undefined : prefilledQuestion,
      userId: user.uid,
      tenant,
      anchor: anchorRef.current,
    });

    hasFetched.current = true;
  }, [
    sessionId,
    user?.uid,
    chatSession,
    hydrateChatSession,
    messages,
    parties,
    initialQuestion,
    prefilledQuestion,
    tenant,
    anchorKey,
  ]);

  const normalizedMessages = useMemo(() => {
    if (messages && !storeMessages.length) {
      return messages;
    }

    if (!storeMessages.length && initialQuestion) {
      return [
        {
          id: INITIAL_MESSAGE_ID,
          messages: [
            {
              role: 'user',
              content: initialQuestion,
              id: INITIAL_MESSAGE_ID,
              sources: [],
            },
          ],
          role: 'user',
        } satisfies GroupedMessage,
      ];
    }

    return storeMessages;
  }, [messages, storeMessages, initialQuestion]);

  return (
    <ChatMessagesScrollView>
      <div className="flex flex-col gap-6 px-3 py-4 md:px-[35px]">
        {normalizedMessages.length === 0 && (
          <div className="mt-12 flex h-full grow justify-center md:mt-24">
            {feedPicks ? (
              <GeneralChatEmptyView feedPicks={feedPicks} />
            ) : (
              <ChatEmptyView
                parties={parties}
                proposedQuestions={proposedQuestions}
              />
            )}
          </div>
        )}

        {normalizedMessages.map((m, index) => (
          <ChatGroupedMessages
            key={m.id}
            message={m}
            isLastMessage={index === normalizedMessages.length - 1}
            parties={allParties?.filter((p) =>
              m.messages.some((m) => m.party_id === p.party_id),
            )}
          />
        ))}

        {hasCurrentStreamingMessages && <CurrentStreamingMessages />}
      </div>
    </ChatMessagesScrollView>
  );
}

export default ChatMessagesView;
