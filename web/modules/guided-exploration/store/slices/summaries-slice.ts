/**
 * Summaries Slice
 * Manages summary state (synced with Firebase) per exploration.
 */

import type {
  ExplorationAction,
  SummariesSliceState,
} from '@/modules/guided-exploration/store/types';

export const initialSummariesState: SummariesSliceState = {
  summaries: {},
  topicSummaries: {},
  generatingIds: [],
};

export function summariesReducer(
  state: SummariesSliceState,
  action: ExplorationAction,
): SummariesSliceState {
  switch (action.type) {
    case 'SUMMARY_GENERATING':
      return {
        ...state,
        generatingIds: state.generatingIds.includes(action.nodeId)
          ? state.generatingIds
          : [...state.generatingIds, action.nodeId],
      };

    case 'SUMMARY_GENERATION_DONE':
      return {
        ...state,
        generatingIds: state.generatingIds.filter((id) => id !== action.nodeId),
      };

    case 'LEAF_SUMMARY_RECEIVED': {
      const existing = state.summaries[action.explorationId] ?? {};
      return {
        ...state,
        summaries: {
          ...state.summaries,
          [action.explorationId]: {
            ...existing,
            [action.leafId]: action.summary,
          },
        },
        generatingIds: state.generatingIds.filter((id) => id !== action.leafId),
      };
    }

    case 'TOPIC_SUMMARY_RECEIVED': {
      const existing = state.topicSummaries[action.explorationId] ?? {};
      return {
        ...state,
        topicSummaries: {
          ...state.topicSummaries,
          [action.explorationId]: {
            ...existing,
            [action.topicId]: action.summary,
          },
        },
        generatingIds: state.generatingIds.filter(
          (id) => id !== action.topicId,
        ),
      };
    }

    case 'SUMMARIES_SYNCED':
      return {
        ...state,
        summaries: {
          ...state.summaries,
          [action.explorationId]: action.summaries,
        },
      };

    case 'EXPLORATION_ENDED': {
      const summaries = { ...state.summaries };
      const topicSummaries = { ...state.topicSummaries };
      delete summaries[action.explorationId];
      delete topicSummaries[action.explorationId];
      return { ...state, summaries, topicSummaries };
    }

    case 'SUMMARIES_CLEARED':
    case 'SESSION_CLEARED':
      return initialSummariesState;

    default:
      return state;
  }
}
