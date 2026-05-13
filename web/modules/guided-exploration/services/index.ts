/**
 * Services Exports
 */

export {
  SSEClient,
  createSSEClient,
  type SSEClientOptions,
  type SSEEventHandler,
  type SSEErrorHandler,
  type SSEStatusHandler,
} from './sse-client';

export {
  explorationApi,
  createSession,
  getSession,
  getExploration,
  sendMessage,
  submitChoice,
  navigate,
  requestAnalysis,
  endExploration,
  type CreateSessionRequest,
  type CreateSessionResponse,
  type ResumeSessionResponse,
  type GetExplorationResponse,
  type SendMessageRequest,
  type SubmitChoiceRequest,
  type NavigateRequest,
  type RequestAnalysisRequest,
  type ApiError,
} from './exploration-api';
