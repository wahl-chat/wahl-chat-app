/**
 * Form data types for study pages
 */

export interface ConsentData {
  consentGiven: boolean;
}

export type Gender = 'male' | 'female' | 'diverse' | 'prefer_not_to_say';

export type Education =
  | 'no_degree'
  | 'hauptschule'
  | 'realschule'
  | 'abitur'
  | 'bachelor'
  | 'master'
  | 'doctorate'
  | 'other';

export type AgeRange = '18-24' | '25-34' | '35-44' | '45-54' | '55-64' | '65+';

export interface DemographicsData {
  ageRange: AgeRange;
  gender: Gender;
  education: Education;
  politicalInterest: number; // 1-7
}

/**
 * Meta-Artificial Intelligence Literacy Scale – Short Version (MAILS-Short)
 * Koch, Carolus, et al., 2024
 *
 * Trimmed to 4 items (one per subscale: Detect AI, AI Ethics, Apply AI,
 * Understand AI) to keep the pre-task screening short. 11-point
 * self-assessment (0 = gar nicht ausgeprägt, 10 = (nahezu) perfekt).
 */
export interface MailsShortItem {
  /** 1-indexed item number (preserved from the full MAILS-Short scale) */
  id: number;
  /** Verbatim German item text */
  text: string;
}

export interface MailsShortData {
  item1: number; // 0-10 — Detect AI
  item5: number; // 0-10 — AI Ethics
  item7: number; // 0-10 — Apply AI
  item10: number; // 0-10 — Understand AI
}

export const MAILS_SHORT_INTRO = `Im Folgenden liest du Beschreibungen verschiedener Fähigkeiten, die man im Umgang mit künstlicher Intelligenz haben kann. Diese Fähigkeiten können stärker oder schwächer ausgeprägt sein. Bitte bewerte dich selbst: Wie stark sind deine Fähigkeiten ausgeprägt?

Ein Wert von 0 bedeutet, dass eine Fähigkeit gar nicht oder kaum ausgeprägt ist. Ein Wert von 10 bedeutet, dass eine Fähigkeit sehr gut oder (nahezu) perfekt ausgeprägt ist.`;

export const MAILS_SHORT_ITEMS: MailsShortItem[] = [
  {
    id: 1,
    text: 'Ich kann erkennen, ob ich es mit einer Anwendung zu tun habe, die auf KI basiert.',
  },
  {
    id: 5,
    text: 'Ich kann abwägen, welche Konsequenzen die Nutzung von KI für die Gesellschaft hat.',
  },
  {
    id: 7,
    text: 'Ich kann KI sinnvoll einsetzen, um meine Ziele zu erreichen.',
  },
  {
    id: 10,
    text: 'Ich kann einschätzen, welche Vor- und Nachteile der Einsatz einer KI mit sich bringt.',
  },
];

export interface LiteracyData {
  mailsShort: MailsShortData;
}

export interface FeedbackData {
  feedback?: string;
}
