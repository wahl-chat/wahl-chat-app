import type {
  LLMSize,
  PartyResponseChunkReadyPayload,
  StreamingMessage,
  Vote,
} from '@/lib/socket.types';
import type { Timestamp } from 'firebase/firestore';
import type { PartyDetails } from '@/lib/party-details';
import type { WritableDraft } from 'immer';
import type ChatSocket from '@/lib/chat-socket';
import type { ChatSession, Tenant } from '@/lib/firebase/firebase.types';

export type Source = {
  source: string;
  page: number;
  url: string;
  source_document: string;
  document_publish_date: string;
  party_id?: string;
};

export type CurrentStreamingMessages = {
  id: string;
  messages: Record<string, StreamingMessage>;
  chat_title?: string;
  quick_replies?: string[];
  streaming_complete?: boolean;
  responding_party_ids?: string[];
};

export type MessageItem = {
  id: string;
  content: string;
  sources: Source[];
  party_id?: string;
  role: 'assistant' | 'user';
  pro_con_perspective?: MessageItem;
  feedback?: MessageFeedback;
  created_at?: Timestamp;
  voting_behavior?: VotingBehavior;
};

export type CurrentStreamedVotingBehavior = {
  requestId: string;
  summary?: string;
  votes?: Vote[];
};

export type VotingBehavior = {
  summary: string;
  votes: Vote[];
};

export type TtsMessageState = {
  status: 'idle' | 'loading' | 'ready' | 'playing' | 'error';
  audioBase64?: string;
  error?: string;
};

export function getTtsKey(
  sessionId: string,
  partyId: string,
  messageId: string,
): string {
  return `${sessionId}_${partyId}_${messageId}`;
}

export type VoiceTranscriptionStatus = {
  status: 'pending' | 'transcribed' | 'error';
  error?: string;
};

export type GroupedMessage = {
  id: string;
  messages: MessageItem[];
  voice_transcription?: VoiceTranscriptionStatus;
  chat_title?: string;
  quick_replies?: string[];
  role: 'user' | 'assistant';
  created_at?: Timestamp;
};

export type MessageFeedback = {
  feedback: 'like' | 'dislike';
  detail?: string;
};

export type ChatStoreState = {
  userId?: string;
  isAnonymous?: boolean;
  chatSessionId?: string;
  // We set this when we start the chat session, then also initialize the chat session on the server. When sending messages, the
  // preliminary chat session id should be the same as the chat session id.
  localPreliminaryChatSessionId?: string;
  partyIds: Set<string>;
  preSelectedParties?: PartyDetails[];
  messages: GroupedMessage[];
  input: string;
  loading: {
    general: boolean;
    newMessage: boolean;
    proConPerspective: string | undefined;
    votingBehaviorSummary: string | undefined;
    chatSession: boolean;
    initializingChatSocketSession: boolean;
  };
  pendingStreamingMessageTimeoutHandler: {
    interval?: NodeJS.Timeout;
    timeout?: NodeJS.Timeout;
  };
  error?: string;
  pendingInitialQuestion?: string;
  initialQuestionError?: string;
  currentQuickReplies: string[];
  currentChatTitle?: string;
  chatSessionIsPublic?: boolean;
  socket: {
    io?: ChatSocket;
    connected?: boolean;
    error?: string;
    isConnecting?: boolean;
  };
  currentStreamingMessages?: CurrentStreamingMessages;
  currentStreamedVotingBehavior?: CurrentStreamedVotingBehavior;
  clickedProConButton?: boolean;
  clickedVotingBehaviorSummaryButton?: boolean;
  ttsState: Record<string, TtsMessageState>;
  sharingSnapshot?: {
    id: string;
    messagesLengthAtSharing: number;
  };
  tenant?: Tenant;
};

export type ChatStoreActions = {
  setIsAnonymous: (isAnonymous: boolean) => void;
  setInput: (input: string) => void;
  addUserMessage: (
    userId: string,
    message: string,
    fromInitialQuestion?: boolean,
  ) => void;
  setChatSessionId: (chatSessionId: string) => void;
  newChat: () => void;
  loadChatSession: (chatSessionId: string) => Promise<void>;
  hydrateChatSession: ({
    chatSession,
    messages,
    chatSessionId,
    preSelectedPartyIds,
    initialQuestion,
    userId,
    tenant,
  }: {
    chatSession?: ChatSession;
    messages?: GroupedMessage[];
    chatSessionId?: string;
    preSelectedPartyIds?: string[];
    initialQuestion?: string;
    userId: string;
    tenant?: Tenant;
  }) => void;
  generateProConPerspective: (
    partyId: string,
    message: MessageItem | StreamingMessage,
  ) => Promise<void>;
  setChatSessionIsPublic: (isPublic: boolean) => Promise<void>;
  setMessageFeedback: (messageId: string, feedback: MessageFeedback) => void;
  setPreSelectedParties: (parties: PartyDetails[]) => void;
  setSocket: (socket: ChatSocket) => void;
  setSocketConnecting: (isConnecting: boolean) => void;
  setSocketConnected: (connected: boolean) => void;
  setSocketError: (error: string) => void;
  initializeChatSession: () => Promise<void>;
  initializedChatSession: (sessionId: string) => void;
  selectRespondingParties: (sessionId: string, partyIds: string[]) => void;
  streamingMessageSourcesReady: (
    sessionId: string,
    partyId: string,
    sources: Source[],
  ) => void;
  mergeStreamingChunkPayloadForMessage: (
    sessionId: string,
    partyId: string,
    streamingMessage: PartyResponseChunkReadyPayload,
  ) => void;
  updateQuickRepliesAndTitleForCurrentStreamingMessage: (
    sessionId: string,
    quickReplies: string[],
    title: string,
  ) => void;
  completeStreamingMessage: (
    sessionId: string,
    partyId: string,
    completeMessage: string,
    messageId?: string,
  ) => void;
  startTimeoutForStreamingMessages: (streamingMessageId: string) => void;
  cancelStreamingMessages: (streamingMessageId?: string) => void;
  completeProConPerspective: (requestId: string, message: MessageItem) => void;
  generateSharingSnapshotLink: () => Promise<void>;
  generateVotingBehaviorSummary: (
    partyId: string,
    message: MessageItem | StreamingMessage,
  ) => void;
  addVotingBehaviorResult: (
    requestId: string,
    vote: Vote,
    isEnd: boolean,
  ) => void;
  addVotingBehaviorSummaryChunk: (
    requestId: string,
    chunk: string,
    isEnd: boolean,
  ) => void;
  completeVotingBehavior: (
    requestId: string,
    votes: Vote[],
    message: string,
  ) => void;
  setPartyIds: (partyIds: string[]) => void;
  getLLMSize: () => LLMSize;
  sendVoiceMessage: (audioBase64: string) => Promise<void>;
  requestTextToSpeech: (partyId: string, messageId: string) => void;
  setTtsReady: (
    partyId: string,
    messageId: string,
    audioBase64: string,
  ) => void;
  setTtsError: (partyId: string, messageId: string, error: string) => void;
  setTtsPlaying: (partyId: string, messageId: string) => void;
  setTtsIdle: (partyId: string, messageId: string) => void;
  setVoiceTranscriptionPending: (messageId: string) => void;
  setVoiceTranscribed: (
    groupedMessageId: string,
    messageId: string,
    transcribedText: string,
  ) => void;
  setVoiceTranscriptionError: (groupedMessageId: string, error: string) => void;
};

export type ChatStore = ChatStoreState & ChatStoreActions;

export type ChatStoreActionHandlerFor<T extends keyof ChatStoreActions> = (
  get: () => ChatStore,
  set: (
    nextStateOrUpdater:
      | ChatStore
      | Partial<ChatStore>
      | ((state: WritableDraft<ChatStore>) => void),
    shouldReplace?: false,
  ) => void,
) => (
  ...args: Parameters<ChatStoreActions[T]>
) => ReturnType<ChatStoreActions[T]>;
