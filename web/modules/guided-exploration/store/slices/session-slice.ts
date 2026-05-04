/**
 * Session Slice
 * Tracks the session id and chat-level message timeline. With multi-tree
 * inline in the chat there is no longer an "active exploration" pointer
 * or tab list at the session level.
 */

import type {
  ExplorationAction,
  SessionSliceState,
} from '@/modules/guided-exploration/store/types';

export const initialSessionState: SessionSliceState = {
  sessionId: null,
  messages: [],
};

export function sessionReducer(
  state: SessionSliceState,
  action: ExplorationAction,
): SessionSliceState {
  switch (action.type) {
    case 'SESSION_CREATED':
    case 'SESSION_LOADED':
      return { ...state, sessionId: action.sessionId };

    case 'SESSION_CLEARED':
      return initialSessionState;

    case 'SESSION_MESSAGE_ADDED':
      return { ...state, messages: [...state.messages, action.message] };

    case 'SESSION_MESSAGE_UPDATED':
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id === action.messageId ? { ...msg, ...action.updates } : msg,
        ),
      };

    case 'SESSION_MESSAGES_LOADED':
      return { ...state, messages: action.messages };

    default:
      return state;
  }
}
