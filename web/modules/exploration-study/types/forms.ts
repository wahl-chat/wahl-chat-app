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

export type AiChatUsageFrequency =
  | 'never'
  | 'less_than_monthly'
  | 'several_times_per_month'
  | 'several_times_per_week'
  | 'almost_daily';

export interface DemographicsData {
  ageRange: AgeRange;
  gender: Gender;
  education: Education;
  politicalInterest: number; // 1-7
  aiChatUsageFrequency: AiChatUsageFrequency;
}

export interface FeedbackData {
  feedback?: string;
}
