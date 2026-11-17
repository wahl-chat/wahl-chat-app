import type { FeedPick } from '@/lib/chat-feed';
import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import {
  getChatSession,
  getChatSessionMessages,
  getContext,
  getCurrentUser,
  getPartiesForContext,
  getPartiesForContextById,
  getProposedQuestionsForContext,
} from '@/lib/firebase/firebase-server';
import type { ChatAnchor } from '@/lib/firebase/firebase.types';
import { getChatFeedPicks } from '@/lib/server-actions/chat-feed-picks';
import { redirect } from 'next/navigation';
import ChatMessagesView from './chat-messages-view';

type Props = {
  chatSessionId?: string;
  partyIds?: string[];
  initialQuestion?: string;
  prefilledQuestion?: string;
  contextId?: string;
  anchor?: ChatAnchor;
};

async function getChatSessionServer(
  chatSessionId: string,
  contextId: string,
  partyIds?: string[],
) {
  const user = await getCurrentUser();

  if (!user) {
    throw new Error('User not found');
  }

  try {
    const session = await getChatSession(chatSessionId);

    if (!session) {
      throw new Error('Chat session not found');
    }

    return session;
  } catch (error) {
    console.error('Error getting chat session', error);

    const searchParams = new URLSearchParams();
    partyIds?.forEach((partyId) => searchParams.append('party_id', partyId));

    redirect(`/${contextId}/session?${searchParams.toString()}`);
  }
}

async function ChatViewSsr({
  chatSessionId,
  partyIds,
  initialQuestion,
  prefilledQuestion,
  contextId = DEFAULT_CONTEXT_ID,
  anchor,
}: Props) {
  const chatSession = chatSessionId
    ? await getChatSessionServer(chatSessionId, contextId, partyIds)
    : undefined;

  const messages = chatSessionId
    ? await getChatSessionMessages(chatSessionId)
    : undefined;

  const normalizedPartyIds = chatSession?.party_ids ?? partyIds;

  const parties = normalizedPartyIds
    ? await getPartiesForContextById(contextId, normalizedPartyIds)
    : undefined;

  const allParties = await getPartiesForContext(contextId);

  const context = await getContext(contextId);
  const isGeneral = context?.type === 'general';

  // A general chat opens with questions from the feed instead.
  const proposedQuestions = isGeneral
    ? []
    : await getProposedQuestionsForContext(contextId, normalizedPartyIds);
  const feedPicks: FeedPick[] | undefined = isGeneral
    ? await getChatFeedPicks()
    : undefined;

  return (
    <ChatMessagesView
      sessionId={chatSessionId}
      chatSession={chatSession}
      parties={parties}
      allParties={allParties}
      messages={messages}
      proposedQuestions={proposedQuestions}
      feedPicks={feedPicks}
      initialQuestion={initialQuestion}
      prefilledQuestion={prefilledQuestion}
      anchor={anchor}
    />
  );
}

export default ChatViewSsr;
