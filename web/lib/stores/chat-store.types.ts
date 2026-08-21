import type { ChatSession, Tenant } from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import type { ProlificMetadata } from '@/lib/prolific-study/prolific-metadata';
import type {
  LLMSize,
  PartyResponseChunkReadyPayload,
  StreamingMessage,
  Vote,
} from '@/lib/socket.types';
import type { Timestamp } from 'firebase/firestore';
import type { WritableDraft } from 'immer';

export type Source = {
  source: string;
  page: number;
  url: string;
  source_document: string;
  document_publish_date: string;
  party_id?: string;
  // Corpus source category; absent on messages persisted before it shipped.
  source_type?: 'party_manifesto' | 'vote_record' | 'parliamentary_speech';
  // Dual-format speech links (backend merges op video + DIP transcript into ONE
  // source): when both are present the citation renders two quick-links — the
  // video deep-link and the PDF transcript — for the same source. `url` stays the
  // primary (video-first) link for back-compat.
  video_url?: string;
  pdf_url?: string;
  // Leading excerpt of the cited chunk — the PDF viewer's highlight anchor.
  // Absent on votes, Perplexity sources, and messages persisted before it shipped.
  snippet?: string;
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

export type GroupedMessage = {
  id: string;
  messages: MessageItem[];
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
  contextId?: string;
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
  };
  pendingStreamingMessageTimeoutHandler: {
    timeout?: NodeJS.Timeout;
  };
  error?: string;
  pendingInitialQuestion?: string;
  initialQuestionError?: string;
  currentQuickReplies: string[];
  currentChatTitle?: string;
  chatSessionIsPublic?: boolean;
  currentStreamingMessages?: CurrentStreamingMessages;
  currentStreamedVotingBehavior?: CurrentStreamedVotingBehavior;
  clickedProConButton?: boolean;
  clickedVotingBehaviorSummaryButton?: boolean;
  sharingSnapshot?: {
    id: string;
    messagesLengthAtSharing: number;
  };
  tenant?: Tenant;
  prolificMetadata?: ProlificMetadata;
  prolificMinInteractions?: number;
  prolificDisclaimerDismissed?: boolean;
  prolificMessageCount: number;
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
  // Action files deleted; Socket.IO is replaced by SSE.
  initializeChatSession: () => Promise<void>;
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
  ) => void;
  failStreamingMessage: (sessionId: string, partyId: string) => void;
  finishStreamingTurn: () => void;
  startTimeoutForStreamingMessages: (streamingMessageId: string) => void;
  resetStreamingMessageWatchdog: () => void;
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
  setProlificMetadata: (metadata: ProlificMetadata) => void;
  setProlificConfig: (config: { minInteractions: number }) => void;
  setProlificDisclaimerDismissed: (dismissed: boolean) => void;
  incrementProlificMessageCount: () => void;
  setProlificMessageCount: (count: number) => void;
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
