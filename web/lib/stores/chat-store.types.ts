import type {
  ChatSession,
  StudyParticipant,
  Tenant,
} from '@/lib/firebase/firebase.types';
import type { PartyDetails } from '@/lib/party-details';
import type {
  StudyCohort,
  StudyConsentAnswer,
  StudyConsentStage,
  StudyDeclineReason,
} from '@/lib/pledge-study/study-config';
import type { StudyOverride } from '@/lib/pledge-study/variant-override';
import type { ProlificMetadata } from '@/lib/prolific-study/prolific-metadata';
import type {
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

export type PledgeTimelineEvent = {
  date: string;
  publication_date?: string | null;
  event: string;
  event_short?: string | null;
  url?: string | null;
  title?: string | null;
  bundesland?: string | null;
  source?: string | null;
  party?: string | null;
  actor_type?: string | null;
  is_relevant_for_tracking?: boolean | null;
  raw_label?: string | null;
  confidence?: number | null;
};

export type PledgeRecord = {
  pledge_id: string;
  party_id: string;
  claim: string;
  normalized_summary: string;
  region_path: string[];
  region: string;
  context_id?: string | null;
  policy_area?: string | null;
  pledge_date?: string | null;
  pledge_source_title?: string | null;
  pledge_source_url?: string | null;
  pledge_source_locator?: string | null;
  timeline_events: PledgeTimelineEvent[];
  last_checked_at?: string | null;
  tracker_status?: string | null;
  tracker_status_label?: string | null;
  tracker_step?: string | null;
};

export type PledgeTrackerSuggestions = {
  party_id: string;
  pledges: PledgeRecord[];
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
  pledge_tracker?: PledgeTrackerSuggestions;
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
  // --- PledgeTracker study (consent, cohort, questionnaire) ---
  /** Kill-switch snapshot (system_status/pledge_study); undefined = unknown. */
  studyEnabled?: boolean;
  /** undefined = not answered yet (the consent dialog may show). */
  studyConsent?: StudyConsentAnswer;
  studyCohort?: StudyCohort;
  /**
   * Forced variant from a ?sg= link. Seeded once at store construction and
   * never mutated, so no writer can race it. Must NOT be read by any render
   * path: it is absent on the server and present on the client, which would
   * be a hydration mismatch. Everything visible flows through studyConsent /
   * studyCohort / studyEnabled instead.
   */
  studyOverride?: StudyOverride;
  /** study_participants/{uid} has been read for the current uid. */
  studyHydrated?: boolean;
  /** Questionnaire prompts shown so far (mirror of the persisted event log). */
  studyPromptCount: number;
  studyQuestionnaireClicked?: boolean;
  /**
   * The PledgeTracker popup is open. Written for its own sake only — the
   * questionnaire deliberately ignores it, so that prompting cannot depend on
   * a surface just one arm can see. Modal open/close is still captured as
   * telemetry (pledge_modal_open / _close) by chat-single-message.
   */
  pledgeModalOpen: boolean;
  /**
   * Epoch ms when the first answer of THIS chat finished streaming — the
   * anchor for the absolute fallback.
   */
  firstAnswerCompletedAt?: number;
  /**
   * Epoch ms when the PARTICIPANT's second answer finished streaming — the
   * primary questionnaire trigger, i.e. the first moment they have
   * demonstrably engaged rather than merely arrived.
   */
  secondAnswerCompletedAt?: number;
  /**
   * Answers this PARTICIPANT has completed, across chats and reloads: seeded
   * from the persisted event log at hydration and carried through newChat.
   * The per-chat message list cannot do this job — starting a second chat
   * empties it, so a second question asked in a fresh chat went uncounted and
   * never reached the questionnaire.
   */
  studyAnswersCompleted: number;
  /**
   * How many of the CURRENT chat's answers are already in the count above.
   * Reset by newChat, so every chat contributes its answers exactly once.
   */
  sessionAnswersCounted: number;
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
    prefilledQuestion,
    userId,
    tenant,
  }: {
    chatSession?: ChatSession;
    messages?: GroupedMessage[];
    chatSessionId?: string;
    preSelectedPartyIds?: string[];
    /** Sent immediately on hydration. */
    initialQuestion?: string;
    /**
     * Put into the input for the user to send themselves. Ignored when
     * initialQuestion is set — a question is either sent or offered, never both.
     */
    prefilledQuestion?: string;
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
    pledgeTracker?: PledgeTrackerSuggestions,
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
  setProlificMetadata: (metadata: ProlificMetadata) => void;
  setProlificConfig: (config: { minInteractions: number }) => void;
  setProlificDisclaimerDismissed: (dismissed: boolean) => void;
  incrementProlificMessageCount: () => void;
  setProlificMessageCount: (count: number) => void;
  setStudyEnabled: (enabled: boolean) => void;
  setPledgeModalOpen: (open: boolean) => void;
  hydrateStudyParticipant: (userId: string) => Promise<void>;
  acceptStudyConsent: (
    userId: string,
    contextId: string,
    partyIds: string[],
  ) => Promise<void>;
  declineStudyConsent: (
    userId: string,
    contextId: string,
    partyIds: string[],
    decline: { stage: StudyConsentStage; reason: StudyDeclineReason },
  ) => Promise<void>;
  recordStudyEvent: (
    type: string,
    options?: { trigger?: string; merge?: Partial<StudyParticipant> },
  ) => Promise<void>;
  incrementStudyPromptCount: () => void;
  setStudyQuestionnaireClicked: (clicked: boolean) => void;
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
