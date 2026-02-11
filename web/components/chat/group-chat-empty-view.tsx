'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import type { ProposedQuestion } from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import { buildPartyImageUrl } from '@/lib/utils';
import Image from 'next/image';
import InitialSuggestionBubble from './initial-suggestion-bubble';

type Props = {
  parties: PartyDetails[];
  proposedQuestions?: ProposedQuestion[];
};

function GroupChatEmptyView({ parties, proposedQuestions }: Props) {
  const { user } = useAnonymousAuth();
  const addUserMessage = useChatStore((state) => state.addUserMessage);

  function handleSuggestionClick(suggestion: string) {
    if (!user?.uid) return;

    addUserMessage(user.uid, suggestion);
  }

  const imageSize = 75;

  return (
    <>
      <div className="flex grow flex-col items-center justify-center gap-4 px-8">
        <div
          className="relative flex flex-col items-center justify-center"
          style={{
            height: imageSize,
            width: (imageSize * (parties?.length ? parties.length + 1 : 0)) / 2,
          }}
        >
          {parties?.map((party, index) => (
            <Image
              key={party.party_id}
              alt={party.name}
              src={buildPartyImageUrl(party.party_id)}
              width={imageSize}
              height={imageSize}
              className="absolute top-0 aspect-square rounded-full border-2 border-background bg-slate-200 object-contain transition-transform duration-200 ease-in-out hover:z-30 hover:-translate-y-4 hover:scale-125"
              style={{
                backgroundColor: party.background_color,
                left: `${(index * imageSize) / 2}px`,
              }}
            />
          ))}
        </div>
        <p className="text-center">
          Starte deinen Vergleichschat mit folgenden Parteien:
          <br />
          {parties?.map((party, index) => (
            <span key={party.party_id} className="font-semibold">
              {party.name}
              {parties.length > 1 && index < parties.length - 1 && ', '}
            </span>
          ))}
        </p>
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
    </>
  );
}

export default GroupChatEmptyView;
