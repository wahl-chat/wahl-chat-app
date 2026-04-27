/**
 * UI Slice
 * Manages UI state including mode, view, streaming, and notifications
 */

import type {
  ExplorationAction,
  OriginTab,
  UISliceState,
} from '@/modules/guided-exploration/store/types';

export const initialUIState: UISliceState = {
  mode: 'idle',
  view: 'root',
  isStreaming: false,
  streamingTarget: null,
  streamingOriginTab: null,
  streamBuffer: '',
  pendingChoice: null,
  pendingChoiceOriginTab: null,
  quickSummary: null,
  thinkingStage: null,
  thinkingMessage: null,
  thinkingOriginTab: null,
  lastActionTab: null,
  announcement: null,
  announcementId: 0,
  error: null,
  explorationPending: false,
  explorationReadyData: null,
  suggestedQuestions: [],
  suggestedQuestionsOriginTab: null,
  topicSwitchSuggestion: null,
  pendingDirections: null,
};

export function uiReducer(
  state: UISliceState,
  action: ExplorationAction,
): UISliceState {
  switch (action.type) {
    // Mode and View
    case 'MODE_CHANGED':
      return {
        ...state,
        mode: action.mode,
      };

    case 'VIEW_CHANGED':
      return {
        ...state,
        view: action.view,
      };

    case 'EXPLORATION_STARTED':
      return {
        ...state,
        mode: 'exploring',
        view: 'root',
        pendingChoice: null,
        explorationPending: false,
        explorationReadyData: null,
      };

    case 'EXPLORATION_TREE_RECEIVED':
      // Tree received but keep mode as 'chat' - show preview with loading
      return {
        ...state,
        explorationPending: true,
        pendingChoice: null,
      };

    case 'EXPLORATION_READY':
      // Exploration is ready for navigation
      return {
        ...state,
        explorationPending: false,
        explorationReadyData: {
          explorationId: action.explorationId,
          topicsCount: action.topicsCount,
          subtopicsCount: action.subtopicsCount,
          partiesCount: action.partiesCount,
        },
        thinkingStage: null,
        thinkingMessage: null,
        thinkingOriginTab: null,
      };

    case 'EXPLORATION_READY_CLEARED':
      return {
        ...state,
        explorationReadyData: null,
      };

    case 'NAVIGATED_TO_ROOT':
      return {
        ...state,
        view: 'root',
      };

    case 'NAVIGATED_TO_BRANCH':
      return {
        ...state,
        view: 'branch',
      };

    case 'NAVIGATED_TO_LEAF':
    case 'CONVERSATION_OPENED':
      return {
        ...state,
        view: 'leaf',
      };

    // Thinking
    case 'THINKING_STARTED':
      return {
        ...state,
        thinkingStage: action.stage,
        thinkingMessage: action.message,
        // Backend `thinking` events carry no scope, so callers can pass an
        // explicit originTab; otherwise we fall back to the most recent
        // user-action's tab so the indicator only shows on its own surface.
        thinkingOriginTab: action.originTab ?? state.lastActionTab,
        suggestedQuestions: [],
        suggestedQuestionsOriginTab: null,
        topicSwitchSuggestion: null,
        streamBuffer: '',
        isStreaming: false,
        streamingTarget: null,
        streamingOriginTab: null,
      };

    case 'THINKING_ENDED':
      return {
        ...state,
        thinkingStage: null,
        thinkingMessage: null,
        thinkingOriginTab: null,
      };

    // Streaming
    case 'STREAM_STARTED': {
      const newStreamingTarget = {
        streamId: action.streamId,
        type: action.targetType,
        id: action.targetId,
      };
      // Infer scope from the target type when the caller doesn't pass one:
      // `quick_summary` is the chat-tab streamable type; everything else
      // (`followup`, `initial_content`, `analysis`) is leaf-scoped.
      const inferredOrigin: OriginTab =
        action.targetType === 'quick_summary' ? 'chat' : 'leaf';
      return {
        ...state,
        isStreaming: true,
        streamingTarget: newStreamingTarget,
        streamingOriginTab: action.originTab ?? inferredOrigin,
        streamBuffer: '',
      };
    }

    case 'STREAM_CHUNK_RECEIVED': {
      // Only process if this is the active stream
      if (state.streamingTarget?.streamId !== action.streamId) {
        return state;
      }
      const newBuffer = state.streamBuffer + action.chunk;
      return {
        ...state,
        streamBuffer: newBuffer,
        streamingTarget: action.section
          ? { ...state.streamingTarget, section: action.section }
          : state.streamingTarget,
      };
    }

    case 'STREAM_ENDED':
      if (state.streamingTarget?.streamId !== action.streamId) {
        return state;
      }
      return {
        ...state,
        isStreaming: false,
        streamingTarget: null,
        streamingOriginTab: null,
      };

    case 'STREAM_BUFFER_CLEARED':
      return {
        ...state,
        streamBuffer: '',
        streamingOriginTab: null,
      };

    // Choice
    case 'CHOICE_PROMPTED':
      return {
        ...state,
        mode: 'choosing',
        pendingChoice: action.choice,
        // Choice prompts (summarize-vs-explore) are always chat-tab events.
        pendingChoiceOriginTab: action.originTab ?? 'chat',
        thinkingStage: null,
        thinkingMessage: null,
        thinkingOriginTab: null,
      };

    case 'CHOICE_CLEARED':
      return {
        ...state,
        pendingChoice: null,
        pendingChoiceOriginTab: null,
      };

    // Quick Summary
    case 'QUICK_SUMMARY_RECEIVED':
      return {
        ...state,
        quickSummary: action.data,
        mode: 'chat',
      };

    case 'QUICK_SUMMARY_CLEARED':
      return {
        ...state,
        quickSummary: null,
      };

    // Announcements
    case 'ANNOUNCE':
      return {
        ...state,
        announcement: action.message,
        announcementId: state.announcementId + 1,
      };

    case 'ANNOUNCEMENT_CLEARED':
      return {
        ...state,
        announcement: null,
      };

    // Errors
    case 'ERROR_OCCURRED':
      return {
        ...state,
        error: {
          code: action.code,
          message: action.message,
          recoverable: action.recoverable,
        },
        isStreaming: false,
        streamingOriginTab: null,
        thinkingStage: null,
        thinkingMessage: null,
        thinkingOriginTab: null,
      };

    case 'ERROR_CLEARED':
      return {
        ...state,
        error: null,
      };

    // Suggested Questions
    case 'SUGGESTED_QUESTIONS_SET':
      return {
        ...state,
        suggestedQuestions: action.questions,
        suggestedQuestionsOriginTab: action.originTab ?? state.lastActionTab,
      };

    case 'SUGGESTED_QUESTIONS_CLEARED':
      return {
        ...state,
        suggestedQuestions: [],
        suggestedQuestionsOriginTab: null,
      };

    case 'LAST_ACTION_TAB_SET':
      return {
        ...state,
        lastActionTab: action.tab,
      };

    case 'TOPIC_SWITCH_SUGGESTED':
      return {
        ...state,
        topicSwitchSuggestion: {
          targetNodeId: action.targetNodeId,
          targetNodeName: action.targetNodeName,
          message: action.message,
        },
      };

    case 'TOPIC_SWITCH_CLEARED':
      return {
        ...state,
        topicSwitchSuggestion: null,
      };

    case 'TOPIC_DIRECTIONS_RECEIVED':
      return {
        ...state,
        pendingDirections: action.directions,
        thinkingStage: null,
        thinkingMessage: null,
      };

    case 'TOPIC_DIRECTIONS_CLEARED':
      return {
        ...state,
        pendingDirections: null,
      };

    // Reset on session clear
    case 'SESSION_CLEARED':
    case 'EXPLORATION_ENDED':
      return {
        ...initialUIState,
        mode: state.mode === 'exploring' ? 'idle' : state.mode,
      };

    default:
      return state;
  }
}
