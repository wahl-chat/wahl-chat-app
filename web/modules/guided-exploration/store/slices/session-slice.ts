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
  explorationTabs: {},
  activeTabId: 'chat',
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
      // Don't set explorationId here — this is just a tree preview.
      // explorationId gets set when user actually enters the exploration
      // via TAB_SWITCHED or EXPLORATION_STARTED.
      return state;

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

    case 'SESSION_MESSAGE_UPDATED':
      return {
        ...state,
        messages: state.messages.map((msg) =>
          msg.id === action.messageId ? { ...msg, ...action.updates } : msg,
        ),
      };

    case 'SESSION_MESSAGES_LOADED':
      return {
        ...state,
        messages: action.messages,
      };

    case 'TAB_SWITCHED': {
      // Save the current navigation path before switching away
      const currentExpId =
        state.activeTabId !== 'chat' ? state.activeTabId : null;
      const updatedTabs =
        currentExpId && state.explorationTabs[currentExpId]
          ? {
              ...state.explorationTabs,
              [currentExpId]: {
                ...state.explorationTabs[currentExpId],
                lastPath:
                  action.previousPath ??
                  state.explorationTabs[currentExpId].lastPath,
              },
            }
          : state.explorationTabs;

      // Mark the target tab as read
      const targetExpId = action.tabId !== 'chat' ? action.tabId : null;
      const finalTabs =
        targetExpId && updatedTabs[targetExpId]
          ? {
              ...updatedTabs,
              [targetExpId]: {
                ...updatedTabs[targetExpId],
                hasUnread: false,
              },
            }
          : updatedTabs;

      return {
        ...state,
        explorationTabs: finalTabs,
        activeTabId: action.tabId,
        explorationId: action.tabId === 'chat' ? null : action.tabId,
      };
    }

    case 'EXPLORATION_TAB_ADDED': {
      return {
        ...state,
        explorationTabs: {
          ...state.explorationTabs,
          [action.explorationId]: {
            explorationId: action.explorationId,
            label: action.label,
            colorIndex: action.colorIndex,
            hasUnread: true,
            lastPath: [],
          },
        },
      };
    }

    case 'EXPLORATION_TAB_REMOVED': {
      const remaining = Object.fromEntries(
        Object.entries(state.explorationTabs).filter(
          ([id]) => id !== action.explorationId,
        ),
      );
      const wasActive = state.activeTabId === action.explorationId;
      return {
        ...state,
        explorationTabs: remaining,
        activeTabId: wasActive ? 'chat' : state.activeTabId,
        explorationId: wasActive ? null : state.explorationId,
      };
    }

    default:
      return state;
  }
}
