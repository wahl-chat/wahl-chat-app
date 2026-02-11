'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import type { ProposedQuestion } from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import { buildPartyImageUrl } from '@/lib/utils';
import Image from 'next/image';
import GroupChatEmptyView from './group-chat-empty-view';
import InitialSuggestionBubble from './initial-suggestion-bubble';
import Logo from './logo';

type Props = {
  parties?: PartyDetails[];
  proposedQuestions?: ProposedQuestion[];
};

function ChatEmptyView({ parties, proposedQuestions }: Props) {
  const { user } = useAnonymousAuth();
  const addUserMessage = useChatStore((state) => state.addUserMessage);

  function handleSuggestionClick(suggestion: string) {
    if (!user?.uid) return;

    addUserMessage(user.uid, suggestion);
  }

  if (parties && parties.length > 1) {
    return (
      <GroupChatEmptyView
        parties={parties}
        proposedQuestions={proposedQuestions}
      />
    );
  }

  const party = parties?.[0];

  return (
    <div className="flex grow flex-col items-center justify-center gap-4 px-8">
      <div
        style={{ backgroundColor: party?.background_color }}
        className="relative flex size-28 items-center justify-center rounded-md border border-muted-foreground/20 bg-background md:size-36"
      >
        {party ? (
          <Image
            alt={party.name}
            src={buildPartyImageUrl(party.party_id)}
            fill
            sizes="(max-width: 768px) 40vw, 20vw"
            className="object-contain p-4"
          />
        ) : (
          <Logo className="size-full p-4" />
        )}
      </div>
      {party ? (
        <p className="text-center">
          Stelle dem Wahlprogramm der Partei{' '}
          <span className="font-semibold">{party.name}</span> deine Fragen und
          vergleiche ihre Antworten mit denen anderer Parteien.
        </p>
      ) : (
        <p className="text-center">
          Stelle Fragen zu allen Themen rund um die{' '}
          <span className="font-semibold">Bundestagswahl 2025</span> oder frage
          die Parteien direkt zu ihren Positionen im Wahlprogramm.
        </p>
      )}
      <div className="flex max-w-xl flex-wrap justify-center gap-2">
        {proposedQuestions?.map((question) => (
          <InitialSuggestionBubble
            key={question.id}
            onClick={() => handleSuggestionClick(question.content)}
          >
            {question.content}
          </InitialSuggestionBubble>
        ))}
      </div>
    </div>
  );
}

export default ChatEmptyView;
