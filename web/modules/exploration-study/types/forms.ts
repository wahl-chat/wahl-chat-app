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

export type ChatbotUsage = 'never' | 'rarely' | 'monthly' | 'weekly' | 'daily';

export type NewsSource =
  | 'online'
  | 'tv'
  | 'newspaper'
  | 'social_media'
  | 'radio';

export interface PoliticalLiteracyAnswers {
  lit_1: string; // Answer to "Wie viele Stimmen hat man bei der Bundestagswahl?"
  lit_2: string; // Answer to "Welches Organ wählt den Bundeskanzler?"
  lit_3: string; // Answer to "Wie lange dauert eine Legislaturperiode des Bundestags?"
}

export interface LiteracyData {
  aiFamiliarity: number; // 1-7: How familiar are you with AI systems?
  chatbotUsage: ChatbotUsage;
  newsConsumption: NewsSource[]; // Multiple sources allowed
  politicalLiteracyAnswers: PoliticalLiteracyAnswers;
}

export interface FeedbackData {
  feedback?: string;
}
