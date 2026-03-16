/**
 * Session Slice
 * Manages session and preferences state
 */

import type {
  ExplorationAction,
  SessionSliceState,
} from '@/modules/guided-exploration/store/types';

export const initialSessionState: SessionSliceState = {
  sessionId: null,
  explorationId: null,
  messages: [],
};

export function sessionReducer(
  state: SessionSliceState,
  action: ExplorationAction,
): SessionSliceState {
  switch (action.type) {
    case 'SESSION_CREATED':
      return {
        ...state,
        sessionId: action.sessionId,
      };

    case 'SESSION_LOADED':
      return {
        ...state,
        sessionId: action.sessionId,
        explorationId: action.explorationId ?? state.explorationId,
      };

    case 'SESSION_CLEARED':
      return initialSessionState;

    case 'EXPLORATION_STARTED':
      return {
        ...state,
        explorationId: action.explorationId,
      };

    case 'EXPLORATION_TREE_RECEIVED':
      return {
        ...state,
        explorationId: action.explorationId,
      };

    case 'EXPLORATION_ENDED':
      return {
        ...state,
        explorationId: null,
      };

    case 'SESSION_MESSAGE_ADDED':
      return {
        ...state,
        messages: [...state.messages, action.message],
      };

    case 'SESSION_MESSAGES_LOADED':
      return {
        ...state,
        messages: action.messages,
      };

    default:
      return state;
  }
}
