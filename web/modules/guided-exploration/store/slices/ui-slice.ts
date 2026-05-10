/**
 * UI Slice
 * Manages UI state: mode, streaming, thinking, and per-message singletons.
 */

import type {
  ExplorationAction,
  OriginTab,
  UISliceState,
} from '@/modules/guided-exploration/store/types';

export const initialUIState: UISliceState = {
  mode: 'idle',
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
  closurePrompt: null,
  pendingDirections: null,
};

export function uiReducer(
  state: UISliceState,
  action: ExplorationAction,
): UISliceState {
  switch (action.type) {
    case 'MODE_CHANGED':
      return { ...state, mode: action.mode };

    case 'EXPLORATION_STARTED':
      return {
        ...state,
        mode: 'exploring',
        pendingChoice: null,
        explorationPending: false,
        explorationReadyData: null,
      };

    case 'EXPLORATION_TREE_RECEIVED':
      return { ...state, explorationPending: true, pendingChoice: null };

    case 'EXPLORATION_READY':
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
      return { ...state, explorationReadyData: null };

    case 'LEAF_ACTIVATED':
    case 'LEAF_OPENED':
      // Opening a (potentially different) leaf invalidates leaf-scoped
      // singletons. Otherwise stale topic-switch suggestions and
      // suggested-question lists from the previous leaf would render.
      return {
        ...state,
        topicSwitchSuggestion: null,
        closurePrompt: null,
        suggestedQuestions:
          state.suggestedQuestionsOriginTab === 'leaf'
            ? []
            : state.suggestedQuestions,
        suggestedQuestionsOriginTab:
          state.suggestedQuestionsOriginTab === 'leaf'
            ? null
            : state.suggestedQuestionsOriginTab,
      };

    case 'LEAF_CLOSED':
      return {
        ...state,
        topicSwitchSuggestion: null,
        closurePrompt: null,
        suggestedQuestions:
          state.suggestedQuestionsOriginTab === 'leaf'
            ? []
            : state.suggestedQuestions,
        suggestedQuestionsOriginTab:
          state.suggestedQuestionsOriginTab === 'leaf'
            ? null
            : state.suggestedQuestionsOriginTab,
      };

    case 'THINKING_STARTED':
      return {
        ...state,
        thinkingStage: action.stage,
        thinkingMessage: action.message,
        thinkingOriginTab: action.originTab ?? state.lastActionTab,
        suggestedQuestions: [],
        suggestedQuestionsOriginTab: null,
        topicSwitchSuggestion: null,
        // A new turn invalidates the previous closure judgement — the
        // upcoming response decides afresh whether the leaf is done.
        closurePrompt: null,
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

    case 'STREAM_STARTED': {
      const inferredOrigin: OriginTab =
        action.targetType === 'quick_summary' ? 'chat' : 'leaf';
      return {
        ...state,
        isStreaming: true,
        streamingTarget: {
          streamId: action.streamId,
          type: action.targetType,
          id: action.targetId,
          explorationId: action.explorationId,
          leafId: action.leafId,
        },
        streamingOriginTab: action.originTab ?? inferredOrigin,
        streamBuffer: '',
      };
    }

    case 'STREAM_CHUNK_RECEIVED': {
      if (state.streamingTarget?.streamId !== action.streamId) {
        return state;
      }
      return {
        ...state,
        streamBuffer: state.streamBuffer + action.chunk,
        streamingTarget: action.section
          ? { ...state.streamingTarget, section: action.section }
          : state.streamingTarget,
      };
    }

    case 'STREAM_ENDED':
      if (state.streamingTarget?.streamId !== action.streamId) {
        return state;
      }
      // Keep `streamingTarget` and `streamingOriginTab` populated until the
      // buffer is cleared (on the final chat_message / conversation_message)
      // so the streaming buffer keeps rendering during the gap between
      // stream_end and the message commit. Clearing them here would null
      // out the routing target and hide the buffer for the consumer hooks.
      return { ...state, isStreaming: false };

    case 'STREAM_BUFFER_CLEARED':
      return {
        ...state,
        streamBuffer: '',
        streamingTarget: null,
        streamingOriginTab: null,
      };

    case 'CHOICE_PROMPTED':
      return {
        ...state,
        mode: 'choosing',
        pendingChoice: action.choice,
        pendingChoiceOriginTab: action.originTab ?? 'chat',
        thinkingStage: null,
        thinkingMessage: null,
        thinkingOriginTab: null,
      };

    case 'CHOICE_CLEARED':
      return { ...state, pendingChoice: null, pendingChoiceOriginTab: null };

    case 'QUICK_SUMMARY_RECEIVED':
      return { ...state, quickSummary: action.data, mode: 'chat' };

    case 'QUICK_SUMMARY_CLEARED':
      return { ...state, quickSummary: null };

    case 'ANNOUNCE':
      return {
        ...state,
        announcement: action.message,
        announcementId: state.announcementId + 1,
      };

    case 'ANNOUNCEMENT_CLEARED':
      return { ...state, announcement: null };

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
      return { ...state, error: null };

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
      return { ...state, lastActionTab: action.tab };

    case 'TOPIC_SWITCH_SUGGESTED':
      return {
        ...state,
        topicSwitchSuggestion: {
          explorationId: action.explorationId,
          leafId: action.leafId,
          targetNodeId: action.targetNodeId,
          targetNodeName: action.targetNodeName,
          message: action.message,
        },
      };

    case 'TOPIC_SWITCH_CLEARED':
      return { ...state, topicSwitchSuggestion: null };

    case 'CLOSURE_PROMPT_SHOWN':
      return {
        ...state,
        closurePrompt: {
          explorationId: action.explorationId,
          leafId: action.leafId,
        },
      };

    case 'CLOSURE_PROMPT_CLEARED':
      return { ...state, closurePrompt: null };

    case 'TOPIC_DIRECTIONS_RECEIVED':
      return {
        ...state,
        pendingDirections: action.directions,
        thinkingStage: null,
        thinkingMessage: null,
      };

    case 'TOPIC_DIRECTIONS_CLEARED':
      return { ...state, pendingDirections: null };

    case 'SESSION_CLEARED':
      return initialUIState;

    case 'EXPLORATION_ENDED':
      // A specific exploration ended — clear leaf-scoped singletons
      // tied to it and drop streaming if it was for that exploration.
      if (state.streamingTarget?.explorationId === action.explorationId) {
        return {
          ...initialUIState,
          mode: state.mode === 'exploring' ? 'idle' : state.mode,
        };
      }
      return {
        ...state,
        topicSwitchSuggestion:
          state.topicSwitchSuggestion?.explorationId === action.explorationId
            ? null
            : state.topicSwitchSuggestion,
      };

    default:
      return state;
  }
}
