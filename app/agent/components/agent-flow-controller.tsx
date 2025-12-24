'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import ConsentScreen from './consent-screen';
import DataCollectionForm from './data-collection-form';
import TopicSelection from './topic-selection';
import AgentChatView from './agent-chat-view';
import CompletionScreen from './completion-screen';

export default function AgentFlowController() {
  const step = useAgentStore((state) => state.step);

  switch (step) {
    case 'consent':
      return <ConsentScreen />;
    case 'data-collection':
      return <DataCollectionForm />;
    case 'topic-selection':
      return <TopicSelection />;
    case 'chat':
      return <AgentChatView />;
    case 'completed':
      return <CompletionScreen />;
    default:
      return <ConsentScreen />;
  }
}


