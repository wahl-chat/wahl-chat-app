'use client';

import { useAnonymousAuth } from '@/components/anonymous-auth';
import { useChatStore } from '@/components/providers/chat-store-provider';
import {
  type FeedPick,
  type StarterQuestion,
  starterQuestions,
} from '@/lib/chat-feed';
import { useMemo } from 'react';
import GeneralChatFeedRow from './general-chat-feed-row';
import InitialSuggestionBubble from './initial-suggestion-bubble';
import Logo from './logo';

type Props = {
  feedPicks: FeedPick[];
};

function GeneralChatEmptyView({ feedPicks }: Props) {
  const { user } = useAnonymousAuth();
  const addUserMessage = useChatStore((state) => state.addUserMessage);
  const setAnchor = useChatStore((state) => state.setAnchor);
  const anchor = useChatStore((state) => state.anchor);
  const anchorItemId =
    anchor && 'feed_item_id' in anchor ? anchor.feed_item_id : undefined;

  const questions = useMemo(
    () => starterQuestions(feedPicks, anchorItemId),
    [feedPicks, anchorItemId],
  );

  function handleClick({ question, feedItemId }: StarterQuestion) {
    if (!user?.uid) return;
    // A question from a feed item is about that item.
    if (feedItemId && feedItemId !== anchorItemId) {
      setAnchor({ feed_item_id: feedItemId });
    }
    addUserMessage(user.uid, question);
  }

  return (
    <div className="flex w-full grow flex-col items-center justify-center gap-4 md:px-8">
      <div className="relative flex size-28 items-center justify-center rounded-md border border-muted-foreground/20 bg-background md:size-36">
        <Logo className="size-full p-4" />
      </div>
      <p className="px-5 text-center md:px-0">
        Stelle Fragen zum aktuellen Geschehen im Bundestag: zu Debatten,
        Abstimmungen und den Positionen der Fraktionen.
      </p>
      <div className="flex max-w-xl flex-wrap justify-center gap-2">
        {questions.map((starter) => (
          <InitialSuggestionBubble
            key={starter.question}
            onClick={() => handleClick(starter)}
          >
            {starter.question}
          </InitialSuggestionBubble>
        ))}
      </div>
      <GeneralChatFeedRow picks={feedPicks} />
    </div>
  );
}

export default GeneralChatEmptyView;
