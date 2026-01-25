import type { ExampleQuestionShareableChatSession } from '@/lib/firebase/firebase.types';
import { InternalReferrers } from '@/lib/internal-referrers';
import Link from 'next/link';
import { useMemo } from 'react';
import TopicTag from './topic-tag';
import type { Topic } from './topics.data';

export type Question = {
  id: string;
  question: string;
  title: string;
  topic: Topic;
};

type Props = {
  exampleQuestionShareableChatSession: ExampleQuestionShareableChatSession;
};

function TopicQuestionCard({ exampleQuestionShareableChatSession }: Props) {
  const { question, topic } = exampleQuestionShareableChatSession;

  const link = useMemo(() => {
    const searchParams = new URLSearchParams();

    searchParams.append('snapshot_id', exampleQuestionShareableChatSession.id);
    searchParams.append('ref', InternalReferrers.TOPICS);

    return `/share?${searchParams.toString()}`;
  }, [exampleQuestionShareableChatSession.id]);

  return (
    <Link
      href={link}
      className="group flex cursor-pointer flex-col gap-2 rounded-md border border-border p-4 text-start ring-offset-background transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <TopicTag topic={topic} />
      <h2 className="font-bold group-hover:underline">{question}</h2>
    </Link>
  );
}

export default TopicQuestionCard;
