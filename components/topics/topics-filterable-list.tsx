'use client';

import type { ExampleQuestionShareableChatSession } from '@/lib/firebase/firebase.types';
import { useMemo, useState } from 'react';
import TopicQuestionCard from './topic-question-card';
import TopicTag from './topic-tag';
import { TOPIC_TITLES, type Topic } from './topics.data';

type TopicsFilterableListProps = {
  exampleQuestionsShareableChatSessions: ExampleQuestionShareableChatSession[];
};

function TopicsFilterableList({
  exampleQuestionsShareableChatSessions,
}: TopicsFilterableListProps) {
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);

  const filteredTopics = useMemo(() => {
    let topics = exampleQuestionsShareableChatSessions;

    if (selectedTopic) {
      topics = topics.filter((session) => selectedTopic === session.topic);
    }

    return topics;
  }, [selectedTopic, exampleQuestionsShareableChatSessions]);

  const handleTopicClick = (topic: Topic) => {
    if (selectedTopic === topic) {
      setSelectedTopic(null);
    } else {
      setSelectedTopic(topic);
    }
  };

  const topics = useMemo(() => {
    return (Object.keys(TOPIC_TITLES) as Topic[]).sort((a, b) =>
      a.localeCompare(b),
    );
  }, []);

  return (
    <>
      <div className="mt-4 flex flex-row flex-wrap gap-2 overflow-x-auto pb-4">
        {topics.map((topic) => (
          <TopicTag
            key={topic}
            topic={topic}
            active={selectedTopic === topic}
            onClick={() => handleTopicClick(topic as Topic)}
          />
        ))}
      </div>

      <section className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {filteredTopics.map((session) => (
          <TopicQuestionCard
            key={session.id}
            exampleQuestionShareableChatSession={session}
          />
        ))}
      </section>
    </>
  );
}

export default TopicsFilterableList;
