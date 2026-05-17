/**
 * Study session types
 */

export type StudyState =
  | 'consent'
  | 'demographics'
  | 'tutorial'
  | 'task'
  | 'questionnaire'
  | 'quiz'
  | 'complete';

export type StudyCondition = 'guided' | 'baseline';

export type StudyTopic = 'klimaschutz' | 'soziale-gerechtigkeit';

// Whether the study collects purely quantitative data or also adds qualitative
// free-text fields to the questionnaires. Set by the backend; the frontend
// treats a missing value as 'quantitative'.
export type StudyType = 'quantitative' | 'qualitative';

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
  chatId: string | null;
  taskDurationSeconds: number;
  // Optional: backend marks the study as quantitative or qualitative.
  // Frontend treats a missing value as 'quantitative'.
  studyType?: StudyType;
}

export interface StudyProgress {
  currentStep: number;
  totalSteps: number;
  stepLabel: string;
}

export const STUDY_STEPS: StudyState[] = [
  'consent',
  'tutorial',
  'task',
  'questionnaire',
  'quiz',
  'demographics',
  'complete',
];

export const STEP_LABELS: Record<StudyState, string> = {
  consent: 'Einwilligung',
  demographics: 'Demografische Angaben',
  tutorial: 'Einführung',
  task: 'Aufgabe',
  questionnaire: 'Fragebogen',
  quiz: 'Quiz',
  complete: 'Abschluss',
};
