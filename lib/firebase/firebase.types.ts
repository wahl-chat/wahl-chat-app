import type { Topic } from '@/components/topics/topics.data';
import type { LLMSize } from '@/lib/socket.types';
import type { GroupedMessage } from '@/lib/stores/chat-store.types';
import type { WahlSwiperResultHistory } from '@/lib/wahl-swiper/wahl-swiper.types';

export type ChatSession = {
  id: string;
  user_id: string;
  party_id?: string;
  is_public?: boolean;
  title?: string;
  created_at?: Date;
  updated_at?: Date;
  party_ids?: string[];
  sharing_snapshot?: {
    id: string;
    messages_length_at_sharing: number;
  };
  tenant_id?: string;
};

export type ShareableChatSessionSnapshot = {
  id: string;
  session_id: string;
  title: string;
  shared_by: string;
  party_ids: string[];
  messages: GroupedMessage[];
  shared_at: Date;
};

export type ProposedQuestion = {
  id: string;
  content: string;
  topic: string;
  location: 'banner' | 'chat' | 'home';
  partyId: string;
};

export type SourceDocument = {
  id: string;
  storage_url: string;
  name: string;
  publish_date?: Date;
  party_id: string;
};

export const DEFAULT_LLM_SIZE: LLMSize = 'large';

export type Tenant = {
  id: string;
  name: string;
  llm_size?: LLMSize;
};

export type ExampleQuestionShareableChatSession = {
  id: string;
  question: string;
  topic: Topic;
};

export type LlmSystemStatus = {
  is_at_rate_limit: boolean;
};

export type FirebaseWahlSwiperResult = {
  id: string;
  user_id: string;
  created_at: Date;
  history: WahlSwiperResultHistory;
};
