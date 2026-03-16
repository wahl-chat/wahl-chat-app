/**
 * Summaries Slice
 * Manages summary state (synced with Firebase)
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

    case 'LEAF_SUMMARY_RECEIVED':
      return {
        ...state,
        summaries: {
          ...state.summaries,
          [action.leafId]: action.summary,
        },
        generatingIds: state.generatingIds.filter((id) => id !== action.leafId),
      };

    case 'TOPIC_SUMMARY_RECEIVED':
      return {
        ...state,
        topicSummaries: {
          ...state.topicSummaries,
          [action.topicId]: action.summary,
        },
        generatingIds: state.generatingIds.filter(
          (id) => id !== action.topicId,
        ),
      };

    case 'SUMMARIES_SYNCED':
      return {
        ...state,
        summaries: action.summaries,
      };

    case 'SUMMARIES_CLEARED':
    case 'SESSION_CLEARED':
    case 'EXPLORATION_ENDED':
      return initialSummariesState;

    default:
      return state;
  }
}
