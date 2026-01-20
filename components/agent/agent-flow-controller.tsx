'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import AgentChatView from './agent-chat-view';
import CompletionScreen from './completion-screen';
import ConsentScreen from './consent-screen';
import ConversationChoiceScreen from './conversation-choice-screen';
import TopicSelection from './topic-selection';

export default function AgentFlowController() {
  const step = useAgentStore((state) => state.step);

  switch (step) {
    case 'consent':
      return <ConsentScreen />;
    case 'conversation-choice':
      return <ConversationChoiceScreen />;
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
