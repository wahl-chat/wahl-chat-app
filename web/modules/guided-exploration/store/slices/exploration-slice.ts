/**
 * Exploration Slice
 * Manages topic tree, navigation, and conversations state
 */

import type {
  ExplorationAction,
  ExplorationSliceState,
} from '@/modules/guided-exploration/store/types';

export const initialExplorationState: ExplorationSliceState = {
  tree: null,
  navigation: null,
  conversations: {},
  activeLeafId: null,
  analysisAvailable: false,
};

export function explorationReducer(
  state: ExplorationSliceState,
  action: ExplorationAction,
): ExplorationSliceState {
  switch (action.type) {
    case 'SESSION_LOADED':
      // Don't load tree/navigation - user starts fresh in chat view
      // They can re-enter any active exploration from there
      return state;

    case 'EXPLORATION_STARTED':
      return {
        ...state,
        tree: action.tree,
        navigation: action.navigation,
        conversations: {},
        activeLeafId: null,
      };

    case 'EXPLORATION_TREE_RECEIVED':
      // Store tree for preview, but don't set navigation (not exploring yet)
      return {
        ...state,
        tree: action.tree,
        conversations: {},
        activeLeafId: null,
      };

    case 'TREE_UPDATED':
      return {
        ...state,
        tree: action.tree,
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

      // Find the initial content message and add analysis to it
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

      const { leafId } = action;
      const parts = leafId.split('.');

      // Update the tree with the new explored status
      const updatedTopics = state.tree.topics.map((topic) => {
        if (parts.length === 1 && topic.id === parts[0]) {
          // Leaf topic (no subtopics) - mark topic as explored
          return { ...topic, status: 'explored' as const };
        }

        if (parts.length >= 2 && topic.id === parts[0]) {
          // Subtopic - find and update it
          const updatedSubtopics = topic.subtopics.map((subtopic) =>
            subtopic.id === leafId
              ? { ...subtopic, status: 'explored' as const }
              : subtopic,
          );

          // Calculate topic status based on subtopics
          const allExplored = updatedSubtopics.every(
            (s) => s.status === 'explored',
          );
          const someExplored = updatedSubtopics.some(
            (s) => s.status === 'explored',
          );
          const topicStatus = allExplored
            ? ('explored' as const)
            : someExplored
              ? ('partial' as const)
              : ('pending' as const);

          return {
            ...topic,
            subtopics: updatedSubtopics,
            status: topicStatus,
          };
        }

        return topic;
      });

      return {
        ...state,
        tree: {
          ...state.tree,
          topics: updatedTopics,
          updatedAt: new Date().toISOString(),
        },
      };
    }

    default:
      return state;
  }
}
