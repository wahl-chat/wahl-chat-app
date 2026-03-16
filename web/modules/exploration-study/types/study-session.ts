/**
 * Study session types
 */

export type StudyState =
  | 'consent'
  | 'demographics'
  | 'literacy'
  | 'tutorial'
  | 'task_1'
  | 'questionnaire_1'
  | 'recall_1'
  | 'quiz_1'
  | 'task_2'
  | 'questionnaire_2'
  | 'recall_2'
  | 'quiz_2'
  | 'preferences'
  | 'complete';

export type StudyCondition = 'guided' | 'chat';

export type StudyTopic = 'klimaschutz' | 'soziale-gerechtigkeit';

export interface TopicInfo {
  id: StudyTopic;
  title: string;
  description: string;
  friendQuestion: string;
}

export const TOPIC_INFO: Record<StudyTopic, TopicInfo> = {
  klimaschutz: {
    id: 'klimaschutz',
    title: 'Klimaschutz',
    description:
      'Maßnahmen zum Schutz des Klimas und zur Bekämpfung des Klimawandels',
    friendQuestion: `Stell dir vor, ein Freund fragt dich:

> „Ich möchte mich über die Positionen der Parteien zum Thema **Klimaschutz** informieren. Kannst du mir einen Überblick geben, was die verschiedenen Parteien dazu sagen? Mich interessiert besonders, welche konkreten Maßnahmen sie vorschlagen und wo die Unterschiede liegen."

Deine Aufgabe ist es, die bereitgestellten Informationen zu erkunden und dir einen Überblick über die Parteipositionen zu verschaffen.`,
  },
  'soziale-gerechtigkeit': {
    id: 'soziale-gerechtigkeit',
    title: 'Soziale Gerechtigkeit',
    description: 'Maßnahmen zur Bekämpfung sozialer Ungleichheit und Armut',
    friendQuestion: `Stell dir vor, ein Freund fragt dich:

> „Ich möchte mich über die Positionen der Parteien zum Thema **Soziale Gerechtigkeit** informieren. Kannst du mir einen Überblick geben, was die verschiedenen Parteien dazu sagen? Mich interessiert besonders, welche Maßnahmen sie gegen Ungleichheit und Armut vorschlagen."

Deine Aufgabe ist es, die bereitgestellten Informationen zu erkunden und dir einen Überblick über die Parteipositionen zu verschaffen.`,
  },
};

export interface StudySession {
  sessionId: string;
  state: StudyState;
  currentState?: StudyState; // Some endpoints return this instead of state
  nextState?: StudyState; // Some endpoints return this for navigation
  group: string;
  currentCondition: StudyCondition | null;
  currentTopic: string | null;
  chatIds: Record<string, string | null>; // { "1": chatId, "2": chatId }
  taskDurationSeconds: number;
}

export interface StudyProgress {
  currentStep: number;
  totalSteps: number;
  stepLabel: string;
}

export const STUDY_STEPS: StudyState[] = [
  'consent',
  'demographics',
  'literacy',
  'tutorial',
  'task_1',
  'questionnaire_1',
  'recall_1',
  'quiz_1',
  'task_2',
  'questionnaire_2',
  'recall_2',
  'quiz_2',
  'preferences',
  'complete',
];

export const STEP_LABELS: Record<StudyState, string> = {
  consent: 'Einwilligung',
  demographics: 'Demografische Angaben',
  literacy: 'Digitale Kompetenz',
  tutorial: 'Einführung',
  task_1: 'Aufgabe 1',
  questionnaire_1: 'Fragebogen 1',
  recall_1: 'Erinnerung 1',
  quiz_1: 'Quiz 1',
  task_2: 'Aufgabe 2',
  questionnaire_2: 'Fragebogen 2',
  recall_2: 'Erinnerung 2',
  quiz_2: 'Quiz 2',
  preferences: 'Präferenzen',
  complete: 'Abschluss',
};
