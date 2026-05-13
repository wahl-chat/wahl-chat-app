/**
 * Exploration API
 * REST API client for guided exploration endpoints
 */

import type { ExplorationTree } from '@/modules/guided-exploration/types';
import {
  keysToCamelCase,
  keysToSnakeCase,
} from '@/modules/guided-exploration/utils/case-conversion';

// ============ Request Types ============

export interface CreateSessionRequest {
  contextId: string;
}

export interface SendMessageRequest {
  content: string;
  /** When provided, message is treated as a follow-up within that leaf's conversation */
  explorationContext?: {
    explorationId: string;
    leafId: string;
  } | null;
}

export interface SubmitChoiceRequest {
  queryId: string;
  choice: 'summary' | 'explore';
}

export interface SubmitDirectionChoiceRequest {
  queryId: string;
  directions: Array<{ id: string; name: string }>;
}

export interface NavigateRequest {
  targetPath: string[];
}

export interface RequestAnalysisRequest {
  leafId: string;
}

// ============ Response Types (camelCase after conversion) ============

export interface CreateSessionResponse {
  sessionId: string;
  streamUrl: string;
}

export interface ResumeSessionResponse {
  sessionId: string;
  streamUrl: string;
  messages: Array<{
    id: string;
    type: 'user' | 'assistant' | 'exploration_start' | 'topic_directions';
    content: string | null;
    citations?: Array<{
      id: string;
      party: string;
      document: string;
      section?: string;
      page?: number;
      url?: string;
    }>;
    explorationId?: string;
    explorationQuery?: string;
    directions?: Array<{
      id: string;
      name: string;
      hook: string;
      suggestedQuestion: string;
    }>;
    directionsQueryId?: string;
    selectedDirections?: string[];
    timestamp: string;
  }>;
  activeExploration?: {
    id: string;
    originalQuery: string;
    status: 'active' | 'completed';
    tree: ExplorationTree;
  };
}

export interface GetExplorationResponse {
  id: string;
  originalQuery: string;
  status: 'active' | 'completed';
  tree: ExplorationTree;
  createdAt: string;
}

// Debug types (camelCase after conversion)
export interface KnowledgeCitation {
  id: string;
  party: string;
  document: string;
  page: number;
  section: string | null;
}

export interface KnowledgePartyPosition {
  party: string;
  /** Full markdown content with inline citations [id] */
  content: string;
}

export interface ResolvedKnowledge {
  leafId: string;
  summaryPoints: string[];
  partyPositions: Record<string, KnowledgePartyPosition>;
  keyFacts: string[];
  citationPool: KnowledgeCitation[];
}

export interface KnowledgeBaseResponse {
  explorationId: string;
  entries: {
    subtopics: Record<string, ResolvedKnowledge>;
  };
}

export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}

// ============ API Client ============

const API_BASE = `${process.env.NEXT_PUBLIC_API_URL}/api/v1/guided-exploration`;

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;

  const { body, ...restOptions } = options;

  const response = await fetch(url, {
    ...restOptions,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    // Convert request body to snake_case
    body: body ? JSON.stringify(keysToSnakeCase(body)) : undefined,
  });

  if (!response.ok) {
    const error: ApiError = await response.json().catch(() => ({
      error: {
        code: 'UNKNOWN_ERROR',
        message: `HTTP ${response.status}: ${response.statusText}`,
      },
    }));
    throw new Error(error.error.message);
  }

  // Handle 202 Accepted (no body expected for async operations)
  if (response.status === 202) {
    return {} as T;
  }

  // Convert response to camelCase
  const data = await response.json();
  return keysToCamelCase<T>(data);
}

// ============ API Methods ============

/**
 * Create a new exploration session
 */
export async function createSession(
  req?: CreateSessionRequest,
): Promise<CreateSessionResponse> {
  return request<CreateSessionResponse>('/sessions', {
    method: 'POST',
    body: req ?? {},
  });
}

/**
 * Load an existing session
 */
export async function getSession(
  sessionId: string,
): Promise<ResumeSessionResponse> {
  return request<ResumeSessionResponse>(`/sessions/${sessionId}`);
}

/**
 * Get a specific exploration with full tree
 */
export async function getExploration(
  sessionId: string,
  explorationId: string,
): Promise<GetExplorationResponse> {
  return request<GetExplorationResponse>(
    `/sessions/${sessionId}/explorations/${explorationId}`,
  );
}

/**
 * Send a message (question or command)
 */
export async function sendMessage(
  sessionId: string,
  req: SendMessageRequest,
): Promise<void> {
  await request(`/sessions/${sessionId}/message`, {
    method: 'POST',
    body: req,
  });
}

/**
 * Submit choice (summary or explore)
 */
export async function submitChoice(
  sessionId: string,
  req: SubmitChoiceRequest,
): Promise<void> {
  await request(`/sessions/${sessionId}/choice`, {
    method: 'POST',
    body: req,
  });
}

/**
 * Submit a topic direction choice
 */
export async function submitDirectionChoice(
  sessionId: string,
  req: SubmitDirectionChoiceRequest,
): Promise<void> {
  await request(`/sessions/${sessionId}/direction-choice`, {
    method: 'POST',
    body: req,
  });
}

/**
 * Navigate to a path in the topic tree
 */
export async function navigate(
  sessionId: string,
  explorationId: string,
  req: NavigateRequest,
): Promise<void> {
  await request(
    `/sessions/${sessionId}/explorations/${explorationId}/navigate`,
    {
      method: 'POST',
      body: req,
    },
  );
}

/**
 * Request analysis for a leaf subtopic
 */
export async function requestAnalysis(
  sessionId: string,
  explorationId: string,
  req: RequestAnalysisRequest,
): Promise<void> {
  await request(
    `/sessions/${sessionId}/explorations/${explorationId}/analysis`,
    {
      method: 'POST',
      body: req,
    },
  );
}

/**
 * End the current exploration
 */
export async function endExploration(
  sessionId: string,
  explorationId: string,
): Promise<void> {
  await request(`/sessions/${sessionId}/explorations/${explorationId}/end`, {
    method: 'POST',
    body: {},
  });
}

/**
 * Mark a leaf as explored
 */
export async function markExplored(
  sessionId: string,
  explorationId: string,
  leafId: string,
): Promise<{ status: string; leafId: string }> {
  return request<{ status: string; leafId: string }>(
    `/sessions/${sessionId}/explorations/${explorationId}/mark-explored`,
    {
      method: 'POST',
      body: { leafId },
    },
  );
}

/**
 * Get the knowledge base for an exploration (debug endpoint)
 */
export async function getKnowledgeBase(
  sessionId: string,
  explorationId: string,
): Promise<KnowledgeBaseResponse> {
  return request<KnowledgeBaseResponse>(
    `/sessions/${sessionId}/explorations/${explorationId}/knowledge-base`,
  );
}

// ============ API Object Export ============

export const explorationApi = {
  createSession,
  getSession,
  getExploration,
  sendMessage,
  submitChoice,
  submitDirectionChoice,
  navigate,
  requestAnalysis,
  endExploration,
  markExplored,
  getKnowledgeBase,
};
