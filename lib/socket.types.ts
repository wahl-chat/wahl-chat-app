import type {
  MessageFeedback,
  MessageItem,
  Source,
  VotingBehavior,
} from './stores/chat-store.types';

export type SourcesReadyPayload = {
  session_id: string;
  sources: Source[];
  party_id: string;
  rag_query: string;
};

export type PartyResponseChunkReadyPayload = {
  session_id: string;
  party_id: string;
  chunk_index: number;
  chunk_content: string;
  is_end: boolean;
};

export type PartyResponseCompletePayload = {
  session_id: string;
  party_id: string;
  complete_message: string;
  message_id?: string;
};

export type QuickRepliesAndTitleReadyPayload = {
  session_id: string;
  quick_replies: string[];
  title: string;
};

export type ProConPerspectiveReadyPayload = {
  request_id: string;
  message: MessageItem;
};

export type CurrentStreamingMessages = {
  id: string;
  messages: Record<string, StreamingMessage>;
  chat_title?: string;
  quick_replies?: string[];
  streaming_complete?: boolean;
};

export type StreamingMessage = {
  id: string;
  role: 'assistant';
  content?: string;
  sources?: Source[];
  party_id?: string;
  chunking_complete?: boolean;
  pro_con_perspective?: MessageItem;
  voting_behavior?: VotingBehavior;
  feedback?: MessageFeedback;
};

export type LLMSize = 'small' | 'large';

export type ChatSessionInitPayload = {
  session_id: string;
  party_ids: string[];
  chat_history: MessageItem[];
  current_title: string;
  chat_response_llm_size: LLMSize;
  last_quick_replies: string[];
};

export type ChatSessionInitializedPayload = {
  session_id: string;
};

export type AddUserMessagePayload = {
  session_id: string;
  id: string;
  user_message?: string;
  party_ids: string[];
  user_is_logged_in: boolean;
  audio_bytes?: Uint8Array;
  grouped_message_id?: string;
  language?: string;
};

export type ProConPerspectiveRequestPayload = {
  request_id: string;
  party_id: string;
  last_assistant_message: string;
  last_user_message: string;
};

export type RespondingPartiesSelectedPayload = {
  session_id: string;
  party_ids: string[];
};

export type VotingBehaviorSummaryChunkPayload = {
  request_id: string;
  summary_chunk: string;
  is_end: boolean;
};

export type VotingBehaviorResultPayload = {
  request_id: string;
  vote: Vote;
  is_end: boolean;
};

export type VotingBehaviorCompletePayload = {
  request_id: string;
  votes: Vote[];
  message: string;
};

type VotingResult = {
  overall: {
    yes: number;
    no: number;
    abstain: number;
    not_voted: number;
    members: number;
  };
  by_party: {
    party: string;
    members: number;
    yes: number;
    no: number;
    abstain: number;
    not_voted: number;
    justification: string;
  }[];
};

type Link = {
  url: string;
  title: string;
};

export type Vote = {
  id: string;
  url: string;
  date: string;
  title: string;
  subtitle: string;
  detail_text: string;
  links: Link[];
  voting_results: VotingResult;
  short_description: string;
  vote_category: string;
  submitting_parties: string[];
};

export type GenerateVotingBehaviorSummaryPayload = {
  request_id: string;
  party_id: string;
  last_user_message: string;
  last_assistant_message: string;
  summary_llm_size: LLMSize;
  user_is_logged_in: boolean;
};

export type TextToSpeechRequestPayload = {
  session_id: string;
  party_id: string;
  message_id: string;
  voice?: string;
};

export type TextToSpeechCompletePayload = {
  session_id: string;
  party_id: string;
  message_id: string;
  audio_base64: string;
  status: {
    indicator: 'success' | 'error';
    message: string;
  };
};

export type VoiceTranscribedPayload = {
  session_id: string;
  grouped_message_id: string;
  message_id: string;
  transcribed_text: string;
};
