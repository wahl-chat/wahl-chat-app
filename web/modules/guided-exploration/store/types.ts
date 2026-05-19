/**
 * Store Types
 * State shapes and action definitions for the exploration store
 */

import type {
  Analysis,
  ChoicePromptEvent,
  Citation,
  Conversation,
  ErrorCode,
  ExplorationOverview,
  ExplorationTree,
  Message,
  SessionMessage,
  StreamSection,
  StreamTargetType,
  ThinkingStage,
  TopicDirectionsEvent,
} from '@/modules/guided-exploration/types';

// ============ State Slices ============

export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'disconnected';

export interface ConnectionSliceState {
  status: ConnectionStatus;
  error: string | null;
  /** Whether this session was claimed by another tab */
  sessionClaimed: boolean;
}

export interface SessionSliceState {
  sessionId: string | null;
  /** Chat messages at session level */
  messages: SessionMessage[];
}

export type ExplorationStatus = 'active' | 'completed' | null;

/** Pointer to the currently open leaf sidebar (one at a time). */
export interface ActiveLeafPointer {
  explorationId: string;
  leafId: string;
}

export interface ExplorationSliceState {
  /** Trees keyed by explorationId. Multiple explorations can be active. */
  trees: Record<string, ExplorationTree>;
  /**
   * Intro + per-party stance summary keyed by explorationId. Ships with
   * the tree event and is rendered alongside the tree card.
   */
  overviews: Record<string, ExplorationOverview>;
  /** Conversations keyed by [explorationId][leafId]. Leaf ids aren't globally unique. */
  conversations: Record<string, Record<string, Conversation>>;
  /** Lifecycle status keyed by explorationId. */
  status: Record<string, ExplorationStatus>;
  /** Currently open leaf sidebar (one at a time). */
  activeLeaf: ActiveLeafPointer | null;
  /** Whether analysis is available, keyed by [explorationId][leafId]. */
  analysisAvailable: Record<string, Record<string, boolean>>;
}

export type AppMode = 'idle' | 'chat' | 'choosing' | 'exploring';

export interface ExplorationReadyData {
  explorationId: string;
  topicsCount: number;
  subtopicsCount: number;
  partiesCount: number;
}

/** Quick summary data stored in state */
export interface QuickSummaryData {
  queryId: string;
  originalQuery: string;
  text: string;
  citations: Citation[];
  canExploreDeeper: boolean;
  suggestedQuestions?: string[];
}

/**
 * Which surface a streaming/thinking event belongs to.
 *
 * - `'chat'`: chat-tab actions (free-form questions, choice prompts,
 *   quick summaries, direction selection).
 * - `'leaf'`: anything scoped to an open leaf conversation inside an
 *   exploration (initial content, follow-ups, leaf analysis).
 * - `null`: unknown / not yet attributed — treat as visible everywhere
 *   for backward compatibility.
 */
export type OriginTab = 'chat' | 'leaf' | null;

/**
 * Snapshot stamped at STREAM_STARTED so conversation writes survive the
 * user closing the leaf sidebar mid-stream. `explorationId`/`leafId` are
 * null for chat-tab streams (quick_summary).
 */
export interface StreamingTarget {
  explorationId: string | null;
  leafId: string | null;
  streamId: string;
  type: StreamTargetType;
  id: string;
  section?: StreamSection;
}

/** Topic-switch suggestion is always scoped to a specific leaf. */
export interface TopicSwitchSuggestion {
  explorationId: string;
  leafId: string;
  targetNodeId: string;
  targetNodeName: string;
  message: string;
}

export interface UISliceState {
  mode: AppMode;
  isStreaming: boolean;
  streamingTarget: StreamingTarget | null;
  /** Origin of the active stream — see {@link OriginTab}. */
  streamingOriginTab: OriginTab;
  streamBuffer: string;
  pendingChoice: ChoicePromptEvent | null;
  /** Origin of the active pending choice. */
  pendingChoiceOriginTab: OriginTab;
  quickSummary: QuickSummaryData | null;
  thinkingStage: ThinkingStage | null;
  thinkingMessage: string | null;
  /** Origin of the active thinking indicator. */
  thinkingOriginTab: OriginTab;
  /**
   * Tab of the most recent user-initiated action. Used as a fallback
   * scope for events that don't carry origin info (notably `thinking`
   * events from the backend, which include only stage + message).
   */
  lastActionTab: OriginTab;
  announcement: string | null;
  /**
   * Monotonically increments on every ANNOUNCE. Lets the live-region
   * consumer re-announce when the same string fires twice in a row.
   */
  announcementId: number;
  error: {
    code: ErrorCode;
    message: string;
    recoverable: boolean;
  } | null;
  /** Tree preview being shown while exploration loads */
  explorationPending: boolean;
  /** Exploration ready data for auto-navigation */
  explorationReadyData: ExplorationReadyData | null;
  /** Suggested follow-up questions to show above the input */
  suggestedQuestions: string[];
  /** Origin of the active suggested-questions list. */
  suggestedQuestionsOriginTab: OriginTab;
  /** Topic switch suggestion from the routing agent (always leaf-scoped). */
  topicSwitchSuggestion: TopicSwitchSuggestion | null;
  /**
   * When non-null, the LLM judged the active leaf substantially
   * explored. The leaf sidebar replaces the chat input with an
   * accessible closure prompt ("Thema abschließen / Weiter erkunden")
   * scoped to this leaf.
   */
  closurePrompt: { explorationId: string; leafId: string } | null;
  /** Pending topic directions for user selection */
  pendingDirections: TopicDirectionsEvent | null;
}

// ============ Combined State ============

export interface ExplorationStoreState {
  connection: ConnectionSliceState;
  session: SessionSliceState;
  exploration: ExplorationSliceState;
  ui: UISliceState;
}

// ============ Actions (Discriminated Union) ============

export type ExplorationAction =
  // Connection Actions
  | { type: 'CONNECTION_INIT' }
  | { type: 'CONNECTION_CONNECTING' }
  | { type: 'CONNECTION_CONNECTED' }
  | { type: 'CONNECTION_DISCONNECTED'; error?: string }
  | { type: 'CONNECTION_RESET' }
  | { type: 'SESSION_CLAIMED'; message?: string }

  // Session Actions
  | { type: 'SESSION_CREATED'; sessionId: string }
  | { type: 'SESSION_LOADED'; sessionId: string }
  | { type: 'SESSION_CLEARED' }
  | { type: 'SESSION_MESSAGE_ADDED'; message: SessionMessage }
  | {
      type: 'SESSION_MESSAGE_UPDATED';
      messageId: string;
      updates: Partial<SessionMessage>;
    }
  | { type: 'SESSION_MESSAGES_LOADED'; messages: SessionMessage[] }

  // Exploration Actions
  | {
      type: 'EXPLORATION_STARTED';
      explorationId: string;
      tree: ExplorationTree;
      overview?: ExplorationOverview | null;
      status?: ExplorationStatus;
    }
  | {
      type: 'EXPLORATION_STATUS_UPDATED';
      explorationId: string;
      status: ExplorationStatus;
    }
  | {
      type: 'EXPLORATION_TREE_RECEIVED';
      tree: ExplorationTree;
      overview?: ExplorationOverview | null;
    }
  | {
      type: 'EXPLORATION_READY';
      explorationId: string;
      topicsCount: number;
      subtopicsCount: number;
      partiesCount: number;
    }
  | { type: 'EXPLORATION_READY_CLEARED' }
  | { type: 'EXPLORATION_ENDED'; explorationId: string }

  // Leaf / Conversation Actions
  | {
      /**
       * User-initiated leaf focus. Only sets `activeLeaf`. Conversation
       * data — if the leaf hasn't been visited yet — arrives later via
       * SSE `conversation_opened` (`LEAF_OPENED`).
       */
      type: 'LEAF_ACTIVATED';
      explorationId: string;
      leafId: string;
    }
  | {
      /**
       * Backend-confirmed leaf open with conversation payload. Seeds the
       * conversation if absent and sets `activeLeaf`.
       */
      type: 'LEAF_OPENED';
      explorationId: string;
      leafId: string;
      conversation: Conversation;
      analysisAvailable: boolean;
    }
  | { type: 'LEAF_CLOSED' }
  | {
      type: 'LEAF_MARKED_EXPLORED';
      explorationId: string;
      leafId: string;
    }
  | {
      type: 'MESSAGE_ADDED';
      explorationId: string;
      leafId: string;
      message: Message;
    }
  | {
      type: 'ANALYSIS_RECEIVED';
      explorationId: string;
      leafId: string;
      analysis: Analysis;
    }

  // Streaming Actions
  | {
      type: 'STREAM_STARTED';
      streamId: string;
      targetType: StreamTargetType;
      targetId: string;
      explorationId: string | null;
      leafId: string | null;
      originTab: OriginTab;
    }
  | {
      type: 'STREAM_CHUNK_RECEIVED';
      streamId: string;
      chunk: string;
      section?: StreamSection;
    }
  | { type: 'STREAM_ENDED'; streamId: string; complete: boolean }
  | { type: 'STREAM_BUFFER_CLEARED' }

  // UI Actions
  | { type: 'MODE_CHANGED'; mode: AppMode }
  | {
      type: 'THINKING_STARTED';
      stage: ThinkingStage;
      message: string;
      originTab?: OriginTab;
    }
  | { type: 'THINKING_ENDED' }
  | {
      type: 'CHOICE_PROMPTED';
      choice: ChoicePromptEvent;
      originTab?: OriginTab;
    }
  | { type: 'CHOICE_CLEARED' }
  | { type: 'QUICK_SUMMARY_RECEIVED'; data: QuickSummaryData }
  | { type: 'ANNOUNCE'; message: string }
  | { type: 'ANNOUNCEMENT_CLEARED' }
  | {
      type: 'ERROR_OCCURRED';
      code: ErrorCode;
      message: string;
      recoverable: boolean;
    }
  | { type: 'ERROR_CLEARED' }
  | {
      type: 'SUGGESTED_QUESTIONS_SET';
      questions: string[];
      originTab?: OriginTab;
    }
  | { type: 'SUGGESTED_QUESTIONS_CLEARED' }
  | { type: 'LAST_ACTION_TAB_SET'; tab: OriginTab }
  | {
      type: 'TOPIC_SWITCH_SUGGESTED';
      explorationId: string;
      leafId: string;
      targetNodeId: string;
      targetNodeName: string;
      message: string;
    }
  | { type: 'TOPIC_SWITCH_CLEARED' }
  | {
      type: 'CLOSURE_PROMPT_SHOWN';
      explorationId: string;
      leafId: string;
    }
  | { type: 'CLOSURE_PROMPT_CLEARED' }
  | { type: 'TOPIC_DIRECTIONS_RECEIVED'; directions: TopicDirectionsEvent }
  | { type: 'TOPIC_DIRECTIONS_CLEARED' };
