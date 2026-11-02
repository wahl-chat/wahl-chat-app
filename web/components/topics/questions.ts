import { DEFAULT_LOCALE, type Locale } from '@/i18n/locales';
import { QUESTIONS_DE } from './questions.de';
import { QUESTIONS_EN } from './questions.en';
import type { Topic } from './topics.data';

/**
 * Example questions per topic. Which topic a question belongs to is fixed
 * here; only the wording differs per language, so the languages cannot
 * disagree about the grouping.
 */
const QUESTION_TOPICS = {
  q1: 'economy_finance',
  q2: 'economy_finance',
  q3: 'economy_finance',
  q4: 'economy_finance',
  q5: 'economy_finance',
  q6: 'social_labor',
  q7: 'social_labor',
  q8: 'social_labor',
  q9: 'social_labor',
  q10: 'social_labor',
  q11: 'education_research',
  q12: 'education_research',
  q13: 'education_research',
  q14: 'education_research',
  q15: 'education_research',
  q16: 'climate_environment',
  q17: 'climate_environment',
  q18: 'climate_environment',
  q19: 'climate_environment',
  q20: 'climate_environment',
  q21: 'health_care',
  q22: 'health_care',
  q23: 'health_care',
  q24: 'health_care',
  q25: 'health_care',
  q26: 'digitalization_tech',
  q27: 'digitalization_tech',
  q28: 'digitalization_tech',
  q29: 'digitalization_tech',
  q30: 'digitalization_tech',
  q31: 'migration_integration',
  q32: 'migration_integration',
  q33: 'migration_integration',
  q34: 'migration_integration',
  q35: 'migration_integration',
  q36: 'security_justice',
  q37: 'security_justice',
  q38: 'security_justice',
  q39: 'security_justice',
  q40: 'security_justice',
  q41: 'foreign_policy_europe',
  q42: 'foreign_policy_europe',
  q43: 'foreign_policy_europe',
  q44: 'foreign_policy_europe',
  q45: 'foreign_policy_europe',
  q46: 'transport_infrastructure',
  q47: 'transport_infrastructure',
  q48: 'transport_infrastructure',
  q49: 'transport_infrastructure',
  q50: 'transport_infrastructure',
  q51: 'housing_rent',
  q52: 'housing_rent',
  q53: 'housing_rent',
  q54: 'housing_rent',
  q55: 'housing_rent',
} as const satisfies Record<string, Topic>;

export type TopicQuestionId = keyof typeof QUESTION_TOPICS;

/** One language's wording, complete by type: a missing id fails the build. */
export type TopicQuestionTexts = Record<TopicQuestionId, string>;

export type TopicQuestion = {
  id: TopicQuestionId;
  question: string;
  topic: Topic;
};

const QUESTION_TEXTS: Record<Locale, TopicQuestionTexts> = {
  de: QUESTIONS_DE,
  en: QUESTIONS_EN,
};

export function getTopicQuestions(locale: Locale): TopicQuestion[] {
  const texts = QUESTION_TEXTS[locale] ?? QUESTION_TEXTS[DEFAULT_LOCALE];

  return (Object.keys(QUESTION_TOPICS) as TopicQuestionId[]).map((id) => ({
    id,
    question: texts[id],
    topic: QUESTION_TOPICS[id],
  }));
}
