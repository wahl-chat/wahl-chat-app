/**
 * State machine utilities for study navigation
 */

import {
  STEP_LABELS,
  STUDY_STEPS,
  type StudySession,
  type StudyState,
} from '@/modules/exploration-study/types';

/**
 * Extract state from API response (handles nextState, currentState, and state fields)
 */
export function getStateFromResponse(
  response: Partial<StudySession>,
): StudyState | null {
  return response.nextState ?? response.currentState ?? response.state ?? null;
}

/**
 * Get the route path for a given study state
 * State represents the CURRENT step to show
 */
export function getRouteForState(sessionId: string, state: StudyState): string {
  const basePath = `/exploration-study/${sessionId}`;

  switch (state) {
    case 'consent':
      return `${basePath}/consent`;
    case 'demographics':
      return `${basePath}/demographics`;
    case 'literacy':
      return `${basePath}/literacy`;
    case 'tutorial':
      return `${basePath}/tutorial`;
    case 'task_1':
      return `${basePath}/task/1`;
    case 'questionnaire_1':
      return `${basePath}/questionnaire/1`;
    case 'recall_1':
      return `${basePath}/recall/1`;
    case 'quiz_1':
      return `${basePath}/quiz/1`;
    case 'task_2':
      return `${basePath}/task/2`;
    case 'questionnaire_2':
      return `${basePath}/questionnaire/2`;
    case 'recall_2':
      return `${basePath}/recall/2`;
    case 'quiz_2':
      return `${basePath}/quiz/2`;
    case 'preferences':
      return `${basePath}/preferences`;
    case 'complete':
      return `${basePath}/complete`;
    default:
      return `${basePath}/consent`;
  }
}

/**
 * Get the study state from a route pathname
 */
export function getStateFromRoute(pathname: string): StudyState | null {
  // Extract the segment after /exploration-study/[sessionId]/
  const match = pathname.match(
    /\/exploration-study\/[^/]+\/(.+?)(?:\/(\d+))?$/,
  );
  if (!match) return null;

  const [, segment, taskNumber] = match;

  switch (segment) {
    case 'consent':
      return 'consent';
    case 'demographics':
      return 'demographics';
    case 'literacy':
      return 'literacy';
    case 'tutorial':
      return 'tutorial';
    case 'task':
      return taskNumber === '1' ? 'task_1' : 'task_2';
    case 'questionnaire':
      return taskNumber === '1' ? 'questionnaire_1' : 'questionnaire_2';
    case 'recall':
      return taskNumber === '1' ? 'recall_1' : 'recall_2';
    case 'quiz':
      return taskNumber === '1' ? 'quiz_1' : 'quiz_2';
    case 'preferences':
      return 'preferences';
    case 'complete':
      return 'complete';
    default:
      return null;
  }
}

/**
 * Get the step number (1-indexed) for a given state
 */
export function getStepNumber(state: StudyState): number {
  const index = STUDY_STEPS.indexOf(state);
  return index >= 0 ? index + 1 : 1;
}

/**
 * Get the total number of steps
 */
export function getTotalSteps(): number {
  return STUDY_STEPS.length;
}

/**
 * Get the label for a given state
 */
export function getStepLabel(state: StudyState): string {
  return STEP_LABELS[state] || '';
}

/**
 * Check if the current path matches the expected state
 */
export function isValidStateForPath(
  pathname: string,
  expectedState: StudyState,
): boolean {
  const routeState = getStateFromRoute(pathname);
  return routeState === expectedState;
}

/**
 * Get the next state after the current one
 */
export function getNextState(currentState: StudyState): StudyState | null {
  const currentIndex = STUDY_STEPS.indexOf(currentState);
  if (currentIndex < 0 || currentIndex >= STUDY_STEPS.length - 1) {
    return null;
  }
  return STUDY_STEPS[currentIndex + 1];
}

/**
 * Get progress information for the current state
 */
export function getProgress(state: StudyState): {
  currentStep: number;
  totalSteps: number;
  percentage: number;
  label: string;
} {
  const currentStep = getStepNumber(state);
  const totalSteps = getTotalSteps();
  const percentage = Math.round((currentStep / totalSteps) * 100);
  const label = getStepLabel(state);

  return {
    currentStep,
    totalSteps,
    percentage,
    label,
  };
}
