/**
 * API client for the exploration study
 */

import type {
  ConsentData,
  DemographicsData,
  FeedbackData,
  LiteracyData,
  QuestionnaireData,
  QuizAnswer,
  QuizData,
  QuizScore,
  StudySession,
} from '@/modules/exploration-study/types';
import {
  keysToCamelCase,
  keysToSnakeCase,
} from '@/modules/guided-exploration/utils/case-conversion';

const API_BASE = '/api/v1/exploration-study/sessions';

interface ApiResponse<T> {
  data?: T;
  error?: string;
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
}

async function fetchApi<T>(
  path: string,
  options?: RequestOptions,
): Promise<ApiResponse<T>> {
  try {
    const url = `${API_BASE}${path}`;
    const { body, ...restOptions } = options ?? {};

    const response = await fetch(url, {
      ...restOptions,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      body: body ? JSON.stringify(keysToSnakeCase(body)) : undefined,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return {
        error:
          errorData.message ||
          `HTTP ${response.status}: ${response.statusText}`,
      };
    }

    const data = await response.json();
    return { data: keysToCamelCase<T>(data) };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : 'Unknown error occurred',
    };
  }
}

export const studyApi = {
  /**
   * Create a new self-serve study session.
   * Participants are identified via Prolific tracking parameters captured
   * from the invitation URL. Repeated calls with the same
   * ``prolificSessionId`` return the existing session.
   */
  createSession: (prolific: {
    prolificPid: string;
    prolificStudyId?: string | null;
    prolificSessionId: string;
  }) =>
    fetchApi<{ sessionId: string; state: string }>('', {
      method: 'POST',
      body: prolific,
    }),

  /**
   * Get the current session state
   */
  getSession: (sessionId: string) => fetchApi<StudySession>(`/${sessionId}`),

  /**
   * Submit consent
   */
  submitConsent: (sessionId: string, data: ConsentData) =>
    fetchApi<StudySession>(`/${sessionId}/consent`, {
      method: 'POST',
      body: data,
    }),

  /**
   * Submit demographics
   */
  submitDemographics: (sessionId: string, data: DemographicsData) =>
    fetchApi<StudySession>(`/${sessionId}/demographics`, {
      method: 'POST',
      body: data,
    }),

  /**
   * Submit literacy data
   */
  submitLiteracy: (sessionId: string, data: LiteracyData) =>
    fetchApi<StudySession>(`/${sessionId}/literacy`, {
      method: 'POST',
      body: data,
    }),

  /**
   * Complete tutorial
   */
  completeTutorial: (sessionId: string) =>
    fetchApi<StudySession>(`/${sessionId}/tutorial`, {
      method: 'POST',
    }),

  /**
   * Start the task - returns the chat_id for the exploration
   */
  startTask: (sessionId: string) =>
    fetchApi<{ chatId: string; condition: string; durationSeconds: number }>(
      `/${sessionId}/task/start`,
      { method: 'POST' },
    ),

  /**
   * End the task
   */
  endTask: (sessionId: string) =>
    fetchApi<StudySession>(`/${sessionId}/task/end`, {
      method: 'POST',
    }),

  /**
   * Submit questionnaire (Cognitive Load + UEQ-S + Manipulation Checks)
   */
  submitQuestionnaire: (sessionId: string, data: QuestionnaireData) =>
    fetchApi<StudySession>(`/${sessionId}/questionnaire`, {
      method: 'POST',
      body: data,
    }),

  /**
   * Get quiz questions (poll until ready)
   */
  getQuiz: (sessionId: string) => fetchApi<QuizData>(`/${sessionId}/quiz`),

  /**
   * Submit quiz answers
   */
  submitQuiz: (sessionId: string, answers: QuizAnswer[]) =>
    fetchApi<StudySession>(`/${sessionId}/quiz`, {
      method: 'POST',
      body: { answers },
    }),

  /**
   * Get the participant's quiz score after submission (used on the
   * feedback page to display how they performed).
   */
  getQuizResult: (sessionId: string) =>
    fetchApi<QuizScore>(`/${sessionId}/quiz-result`),

  /**
   * Submit optional feedback
   */
  submitFeedback: (sessionId: string, data: FeedbackData) =>
    fetchApi<{ message: string }>(`/${sessionId}/feedback`, {
      method: 'POST',
      body: data,
    }),
};
