/**
 * UI Slice
 * Manages UI state including mode, view, streaming, and notifications
 */

import type {
  ExplorationAction,
  UISliceState,
} from '@/modules/guided-exploration/store/types';

export const initialUIState: UISliceState = {
  mode: 'idle',
  view: 'root',
  isStreaming: false,
  streamingTarget: null,
  streamBuffer: '',
  pendingChoice: null,
  quickSummary: null,
  thinkingStage: null,
  thinkingMessage: null,
  announcement: null,
  error: null,
  explorationPending: false,
  explorationReadyData: null,
  suggestedQuestions: [],
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
        suggestedQuestions: [],
        topicSwitchSuggestion: null,
        streamBuffer: '',
        isStreaming: false,
        streamingTarget: null,
      };

    case 'THINKING_ENDED':
      return {
        ...state,
        thinkingStage: null,
        thinkingMessage: null,
      };

    // Streaming
    case 'STREAM_STARTED': {
      const newStreamingTarget = {
        streamId: action.streamId,
        type: action.targetType,
        id: action.targetId,
      };
      console.log(
        '[Reducer] STREAM_STARTED - creating streamingTarget:',
        newStreamingTarget,
      );
      const newState = {
        ...state,
        isStreaming: true,
        streamingTarget: newStreamingTarget,
        streamBuffer: '',
      };
      console.log(
        '[Reducer] STREAM_STARTED - new state.streamingTarget.type:',
        newState.streamingTarget.type,
      );
      return newState;
    }

    case 'STREAM_CHUNK_RECEIVED': {
      // Only process if this is the active stream
      if (state.streamingTarget?.streamId !== action.streamId) {
        console.log(
          '[Reducer] STREAM_CHUNK_RECEIVED ignored - streamId mismatch',
        );
        return state;
      }
      const newBuffer = state.streamBuffer + action.chunk;
      console.log(
        '[Reducer] STREAM_CHUNK_RECEIVED - buffer length:',
        newBuffer.length,
      );
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
      };

    case 'STREAM_BUFFER_CLEARED':
      return {
        ...state,
        streamBuffer: '',
      };

    // Choice
    case 'CHOICE_PROMPTED':
      return {
        ...state,
        mode: 'choosing',
        pendingChoice: action.choice,
        thinkingStage: null,
        thinkingMessage: null,
      };

    case 'CHOICE_CLEARED':
      return {
        ...state,
        pendingChoice: null,
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
        thinkingStage: null,
        thinkingMessage: null,
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
      };

    case 'SUGGESTED_QUESTIONS_CLEARED':
      return {
        ...state,
        suggestedQuestions: [],
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
