/**
 * Exploration Slice
 * Manages exploration tree, navigation, and conversations state
 */

import type {
  ExplorationAction,
  ExplorationSliceState,
} from '@/modules/guided-exploration/store/types';
import type { ExplorationNode } from '@/modules/guided-exploration/types';

export const initialExplorationState: ExplorationSliceState = {
  tree: null,
  navigation: null,
  conversations: {},
  activeLeafId: null,
  analysisAvailable: false,
  status: null,
};

/**
 * Recursively mark a node as explored and update ancestor statuses.
 * Returns a new node tree (immutable).
 */
function markNodeExplored(
  node: ExplorationNode,
  leafId: string,
): ExplorationNode {
  if (node.id === leafId) {
    return { ...node, status: 'explored' };
  }

  if (node.children.length === 0) return node;

  const updatedChildren = node.children.map((child) =>
    markNodeExplored(child, leafId),
  );

  // Check if any child changed
  const changed = updatedChildren.some(
    (child, i) => child !== node.children[i],
  );
  if (!changed) return node;

  return { ...node, children: updatedChildren };
}

export function explorationReducer(
  state: ExplorationSliceState,
  action: ExplorationAction,
): ExplorationSliceState {
  switch (action.type) {
    case 'SESSION_LOADED':
      return state;

    case 'EXPLORATION_STARTED':
      return {
        ...state,
        tree: action.tree,
        navigation: action.navigation,
        conversations: {},
        activeLeafId: null,
        status: action.status ?? 'active',
      };

    case 'EXPLORATION_STATUS_UPDATED':
      return {
        ...state,
        status: action.status,
      };

    case 'EXPLORATION_TREE_RECEIVED':
      return {
        ...state,
        tree: action.tree,
        conversations: {},
        activeLeafId: null,
      };

    case 'NAVIGATED_TO_ROOT':
      return {
        ...state,
        navigation: action.navigation,
        activeLeafId: null,
      };

    case 'NAVIGATED_TO_BRANCH':
      return {
        ...state,
        navigation: action.navigation,
        activeLeafId: null,
      };

    case 'NAVIGATED_TO_LEAF':
      return {
        ...state,
        navigation: action.navigation,
        activeLeafId: action.leafId,
        analysisAvailable: action.analysisAvailable,
        conversations: {
          ...state.conversations,
          [action.leafId]: action.conversation,
        },
      };

    case 'CONVERSATION_OPENED':
      return {
        ...state,
        activeLeafId: action.leafId,
        analysisAvailable: action.analysisAvailable,
        conversations: {
          ...state.conversations,
          [action.leafId]: action.conversation,
        },
      };

    case 'MESSAGE_ADDED': {
      const conversation = state.conversations[action.leafId];
      if (!conversation) return state;

      return {
        ...state,
        conversations: {
          ...state.conversations,
          [action.leafId]: {
            ...conversation,
            messages: [...conversation.messages, action.message],
          },
        },
      };
    }

    case 'ANALYSIS_RECEIVED': {
      const conversation = state.conversations[action.leafId];
      if (!conversation) return state;

      const updatedMessages = conversation.messages.map((msg) => {
        if (msg.type === 'initial_content' && typeof msg.content !== 'string') {
          return {
            ...msg,
            content: {
              ...msg.content,
              analysis: action.analysis,
            },
          };
        }
        return msg;
      });

      return {
        ...state,
        conversations: {
          ...state.conversations,
          [action.leafId]: {
            ...conversation,
            messages: updatedMessages,
          },
        },
      };
    }

    case 'EXPLORATION_ENDED':
      return initialExplorationState;

    case 'SESSION_CLEARED':
      return initialExplorationState;

    case 'LEAF_MARKED_EXPLORED': {
      if (!state.tree) return state;

      const updatedRoot = markNodeExplored(state.tree.root, action.leafId);
      if (updatedRoot === state.tree.root) return state;

      return {
        ...state,
        tree: {
          ...state.tree,
          root: updatedRoot,
          updatedAt: new Date().toISOString(),
        },
      };
    }

    default:
      return state;
  }
}
