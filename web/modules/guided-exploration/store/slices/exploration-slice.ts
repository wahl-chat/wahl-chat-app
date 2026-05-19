/**
 * Exploration Slice
 * Multi-tree state keyed by explorationId. Conversations are nested
 * `[explorationId][leafId]` because leaf ids aren't globally unique.
 */

import type {
  ExplorationAction,
  ExplorationSliceState,
} from '@/modules/guided-exploration/store/types';
import type { ExplorationNode } from '@/modules/guided-exploration/types';

export const initialExplorationState: ExplorationSliceState = {
  trees: {},
  overviews: {},
  conversations: {},
  status: {},
  activeLeaf: null,
  analysisAvailable: {},
};

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

  const changed = updatedChildren.some(
    (child, i) => child !== node.children[i],
  );
  if (!changed) return node;

  return { ...node, children: updatedChildren };
}

// Mirrors the backend transition in navigation.py (`pending`/`loaded` ->
// `started`); leaves `started`/`explored` alone so a re-open never regresses.
function markNodeStarted(
  node: ExplorationNode,
  leafId: string,
): ExplorationNode {
  if (node.id === leafId) {
    if (node.status === 'pending' || node.status === 'loaded') {
      return { ...node, status: 'started' };
    }
    return node;
  }

  if (node.children.length === 0) return node;

  const updatedChildren = node.children.map((child) =>
    markNodeStarted(child, leafId),
  );

  const changed = updatedChildren.some(
    (child, i) => child !== node.children[i],
  );
  if (!changed) return node;

  return { ...node, children: updatedChildren };
}

function omitKey<V>(record: Record<string, V>, key: string): Record<string, V> {
  if (!(key in record)) return record;
  const next = { ...record };
  delete next[key];
  return next;
}

export function explorationReducer(
  state: ExplorationSliceState,
  action: ExplorationAction,
): ExplorationSliceState {
  switch (action.type) {
    case 'EXPLORATION_STARTED': {
      const overviews = action.overview
        ? { ...state.overviews, [action.explorationId]: action.overview }
        : state.overviews;
      return {
        ...state,
        trees: { ...state.trees, [action.explorationId]: action.tree },
        overviews,
        status: {
          ...state.status,
          [action.explorationId]: action.status ?? 'active',
        },
      };
    }

    case 'EXPLORATION_STATUS_UPDATED':
      return {
        ...state,
        status: { ...state.status, [action.explorationId]: action.status },
      };

    case 'EXPLORATION_TREE_RECEIVED': {
      const overviews = action.overview
        ? {
            ...state.overviews,
            [action.tree.explorationId]: action.overview,
          }
        : state.overviews;
      return {
        ...state,
        trees: { ...state.trees, [action.tree.explorationId]: action.tree },
        overviews,
      };
    }

    case 'LEAF_ACTIVATED': {
      const { explorationId, leafId } = action;
      return {
        ...state,
        activeLeaf: { explorationId, leafId },
      };
    }

    case 'LEAF_OPENED': {
      const { explorationId, leafId, conversation, analysisAvailable } = action;
      const explorationConversations = state.conversations[explorationId] ?? {};
      const existing = explorationConversations[leafId];
      // Backend conversation_opened may arrive after a user-typed
      // optimistic message has already been appended. Preserve the longer
      // history (a full backend payload always supersedes an empty seed).
      const shouldOverwrite =
        !existing || conversation.messages.length >= existing.messages.length;
      const nextConversation = shouldOverwrite ? conversation : existing;
      const explorationAnalysis = state.analysisAvailable[explorationId] ?? {};
      const tree = state.trees[explorationId];
      const updatedRoot = tree ? markNodeStarted(tree.root, leafId) : undefined;
      const treesPatch =
        tree && updatedRoot && updatedRoot !== tree.root
          ? {
              trees: {
                ...state.trees,
                [explorationId]: {
                  ...tree,
                  root: updatedRoot,
                  updatedAt: new Date().toISOString(),
                },
              },
            }
          : {};
      return {
        ...state,
        ...treesPatch,
        activeLeaf: { explorationId, leafId },
        conversations: {
          ...state.conversations,
          [explorationId]: {
            ...explorationConversations,
            [leafId]: nextConversation,
          },
        },
        analysisAvailable: {
          ...state.analysisAvailable,
          [explorationId]: {
            ...explorationAnalysis,
            [leafId]: analysisAvailable,
          },
        },
      };
    }

    case 'LEAF_CLOSED':
      return { ...state, activeLeaf: null };

    case 'MESSAGE_ADDED': {
      const { explorationId, leafId, message } = action;
      const conversation = state.conversations[explorationId]?.[leafId];
      if (!conversation) return state;

      return {
        ...state,
        conversations: {
          ...state.conversations,
          [explorationId]: {
            ...state.conversations[explorationId],
            [leafId]: {
              ...conversation,
              messages: [...conversation.messages, message],
            },
          },
        },
      };
    }

    case 'ANALYSIS_RECEIVED': {
      const { explorationId, leafId, analysis } = action;
      const conversation = state.conversations[explorationId]?.[leafId];
      if (!conversation) return state;

      const updatedMessages = conversation.messages.map((msg) => {
        if (msg.type === 'initial_content' && typeof msg.content !== 'string') {
          return {
            ...msg,
            content: { ...msg.content, analysis },
          };
        }
        return msg;
      });

      return {
        ...state,
        conversations: {
          ...state.conversations,
          [explorationId]: {
            ...state.conversations[explorationId],
            [leafId]: { ...conversation, messages: updatedMessages },
          },
        },
      };
    }

    case 'EXPLORATION_ENDED': {
      const { explorationId } = action;
      const wasActive = state.activeLeaf?.explorationId === explorationId;
      return {
        ...state,
        trees: omitKey(state.trees, explorationId),
        overviews: omitKey(state.overviews, explorationId),
        conversations: omitKey(state.conversations, explorationId),
        status: omitKey(state.status, explorationId),
        analysisAvailable: omitKey(state.analysisAvailable, explorationId),
        activeLeaf: wasActive ? null : state.activeLeaf,
      };
    }

    case 'SESSION_CLEARED':
      return initialExplorationState;

    case 'LEAF_MARKED_EXPLORED': {
      const { explorationId, leafId } = action;
      const tree = state.trees[explorationId];
      if (!tree) return state;

      const updatedRoot = markNodeExplored(tree.root, leafId);
      if (updatedRoot === tree.root) return state;

      return {
        ...state,
        trees: {
          ...state.trees,
          [explorationId]: {
            ...tree,
            root: updatedRoot,
            updatedAt: new Date().toISOString(),
          },
        },
      };
    }

    default:
      return state;
  }
}
