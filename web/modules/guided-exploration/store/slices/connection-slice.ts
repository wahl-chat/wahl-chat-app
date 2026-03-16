/**
 * Connection Slice
 * Manages SSE connection state
 */

import type {
  ConnectionSliceState,
  ExplorationAction,
} from '@/modules/guided-exploration/store/types';

export const initialConnectionState: ConnectionSliceState = {
  status: 'idle',
  error: null,
  reconnectAttempts: 0,
  sessionClaimed: false,
};

export function connectionReducer(
  state: ConnectionSliceState,
  action: ExplorationAction,
): ConnectionSliceState {
  switch (action.type) {
    case 'CONNECTION_INIT':
      return {
        ...state,
        status: 'idle',
        error: null,
        reconnectAttempts: 0,
      };

    case 'CONNECTION_CONNECTING':
      return {
        ...state,
        status: 'connecting',
        error: null,
      };

    case 'CONNECTION_CONNECTED':
      return {
        ...state,
        status: 'connected',
        error: null,
        reconnectAttempts: 0,
      };

    case 'CONNECTION_DISCONNECTED':
      return {
        ...state,
        status: 'disconnected',
        error: action.error ?? null,
      };

    case 'CONNECTION_RECONNECT_ATTEMPT':
      return {
        ...state,
        reconnectAttempts: state.reconnectAttempts + 1,
      };

    case 'CONNECTION_RESET':
      return initialConnectionState;

    case 'SESSION_CLAIMED':
      return {
        ...state,
        status: 'disconnected',
        sessionClaimed: true,
        error: action.message ?? 'Session opened in another tab',
      };

    default:
      return state;
  }
}
