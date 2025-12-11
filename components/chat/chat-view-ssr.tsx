import {
  getChatSession,
  getChatSessionMessages,
  getCurrentUser,
  getParties,
  getPartiesById,
  getProposedQuestions,
} from '@/lib/firebase/firebase-server';
import ChatMessagesView from './chat-messages-view';
import { redirect } from 'next/navigation';

type Props = {
  chatSessionId?: string;
  partyIds?: string[];
  initialQuestion?: string;
};

async function getChatSessionServer(
  chatSessionId: string,
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

    redirect(`/session?${searchParams.toString()}`);
  }
}

async function ChatViewSsr({
  chatSessionId,
  partyIds,
  initialQuestion,
}: Props) {
  const chatSession = chatSessionId
    ? await getChatSessionServer(chatSessionId, partyIds)
    : undefined;

  const messages = chatSessionId
    ? await getChatSessionMessages(chatSessionId)
    : undefined;

  const normalizedPartyIds = chatSession?.party_ids ?? partyIds;

  const parties = normalizedPartyIds
    ? await getPartiesById(normalizedPartyIds)
    : undefined;

  const allParties = await getParties();

  const proposedQuestions = await getProposedQuestions(normalizedPartyIds);

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
