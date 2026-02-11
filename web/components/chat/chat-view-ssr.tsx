import { DEFAULT_CONTEXT_ID } from '@/lib/constants';
import {
  getChatSession,
  getChatSessionMessages,
  getCurrentUser,
  getPartiesForContext,
  getPartiesForContextById,
  getProposedQuestionsForContext,
} from '@/lib/firebase/firebase-server';
import { redirect } from 'next/navigation';
import ChatMessagesView from './chat-messages-view';

type Props = {
  chatSessionId?: string;
  partyIds?: string[];
  initialQuestion?: string;
  contextId?: string;
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
  contextId = DEFAULT_CONTEXT_ID,
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

  const proposedQuestions = await getProposedQuestionsForContext(
    contextId,
    normalizedPartyIds,
  );

  return (
    <ChatMessagesView
      sessionId={chatSessionId}
      chatSession={chatSession}
      parties={parties}
      allParties={allParties}
      messages={messages}
      proposedQuestions={proposedQuestions}
      initialQuestion={initialQuestion}
    />
  );
}

export default ChatViewSsr;
