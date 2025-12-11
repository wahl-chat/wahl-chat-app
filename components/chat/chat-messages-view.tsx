'use client';

import type { PartyDetails } from '@/lib/party-details';
import { useEffect, useMemo, useRef } from 'react';
import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import ChatEmptyView from './chat-empty-view';
import ChatGroupedMessages from './chat-grouped-messages';
import ChatMessagesScrollView from './chat-messages-scroll-view';
import CurrentStreamingMessages from './current-streaming-messages';
import type { GroupedMessage } from '@/lib/stores/chat-store.types';
import type {
  ChatSession,
  ProposedQuestion,
} from '@/lib/firebase/firebase.types';
import { INITIAL_MESSAGE_ID } from './chat-single-user-message';
import { useTenant } from '@/components/providers/tenant-provider';

type Props = {
  sessionId?: string;
  chatSession?: ChatSession;
  messages?: GroupedMessage[];
  parties?: PartyDetails[];
  allParties?: PartyDetails[];
  proposedQuestions?: ProposedQuestion[];
  initialQuestion?: string;
};

function ChatMessagesView({
  sessionId,
  chatSession,
  messages,
  parties,
  allParties,
  proposedQuestions,
  initialQuestion,
}: Props) {
  const hasFetched = useRef(false);
  const storeMessages = useChatStore((state) => state.messages);
  const hydrateChatSession = useChatStore((state) => state.hydrateChatSession);
  const { user } = useAnonymousAuth();
  const tenant = useTenant();

  const hasCurrentStreamingMessages = useChatStore(
    (state) => state.currentStreamingMessages !== undefined,
  );

  useEffect(() => {
    if (!user?.uid) return;

    hydrateChatSession({
      chatSession,
      chatSessionId: sessionId,
      messages,
      preSelectedPartyIds: parties?.map((party) => party.party_id),
      initialQuestion,
      userId: user.uid,
      tenant,
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
    tenant,
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
            <ChatEmptyView
              parties={parties}
              proposedQuestions={proposedQuestions}
            />
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
