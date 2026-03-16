/**
 * API client for the exploration study
 */

import type {
  ConsentData,
  DemographicsData,
  LiteracyData,
  PreferencesData,
  QuestionnaireData,
  QuizAnswer,
  QuizData,
  RecallData,
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
   * Start a task - returns the chat_id for the exploration
   */
  startTask: (sessionId: string, taskNumber: 1 | 2) =>
    fetchApi<{ chatId: string; condition: string; durationSeconds: number }>(
      `/${sessionId}/task/${taskNumber}/start`,
      { method: 'POST' },
    ),

  /**
   * End a task
   */
  endTask: (sessionId: string, taskNumber: 1 | 2) =>
    fetchApi<StudySession>(`/${sessionId}/task/${taskNumber}/end`, {
      method: 'POST',
    }),

  /**
   * Submit questionnaire (NASA-TLX + UEQ-S)
   */
  submitQuestionnaire: (
    sessionId: string,
    taskNumber: 1 | 2,
    data: QuestionnaireData,
  ) =>
    fetchApi<StudySession>(`/${sessionId}/questionnaire/${taskNumber}`, {
      method: 'POST',
      body: data,
    }),

  /**
   * Submit free recall
   */
  submitRecall: (sessionId: string, taskNumber: 1 | 2, data: RecallData) =>
    fetchApi<StudySession>(`/${sessionId}/recall/${taskNumber}`, {
      method: 'POST',
      body: data,
    }),

  /**
   * Get quiz questions (poll until ready)
   */
  getQuiz: (sessionId: string, taskNumber: 1 | 2) =>
    fetchApi<QuizData>(`/${sessionId}/quiz/${taskNumber}`),

  /**
   * Submit quiz answers
   */
  submitQuiz: (sessionId: string, taskNumber: 1 | 2, answers: QuizAnswer[]) =>
    fetchApi<StudySession>(`/${sessionId}/quiz/${taskNumber}`, {
      method: 'POST',
      body: { answers },
    }),

  /**
   * Submit preferences
   */
  submitPreferences: (sessionId: string, data: PreferencesData) =>
    fetchApi<StudySession>(`/${sessionId}/preferences`, {
      method: 'POST',
      body: data,
    }),

  /**
   * Complete the study
   */
  completeStudy: (sessionId: string) =>
    fetchApi<StudySession>(`/${sessionId}/complete`, {
      method: 'POST',
    }),
};
