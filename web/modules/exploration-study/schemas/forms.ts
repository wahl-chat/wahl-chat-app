import { z } from 'zod';

const REQUIRED_SELECT = 'Bitte treffe eine Auswahl.';
const REQUIRED_RATING = 'Bitte wähle einen Wert aus.';

// Optional free-text comment, rendered only in qualitative studies. Always
// part of the schema so the form type is stable across study types.
const qualitativeFeedback = z.string().trim().optional();

// ---------------------------------------------------------------------------
// Consent
// ---------------------------------------------------------------------------

export const consentSchema = z.object({
  consentGiven: z.boolean().refine((v) => v === true, {
    message: 'Bitte stimme zu, um fortzufahren.',
  }),
});

export type ConsentFormValues = z.infer<typeof consentSchema>;

// ---------------------------------------------------------------------------
// Tutorial acknowledgement (both conditions)
// ---------------------------------------------------------------------------

export const tutorialAckSchema = z.object({
  understood: z.boolean().refine((v) => v === true, {
    message: 'Bitte bestätige, dass du dies verstanden hast.',
  }),
});

export type TutorialAckFormValues = z.infer<typeof tutorialAckSchema>;

// ---------------------------------------------------------------------------
// Task intro acknowledgement (both conditions)
// ---------------------------------------------------------------------------

export const taskAckSchema = z.object({
  interventionAck: z.boolean().refine((v) => v === true, {
    message: 'Bitte bestätige, dass du dies verstanden hast.',
  }),
});

export type TaskAckFormValues = z.infer<typeof taskAckSchema>;

// ---------------------------------------------------------------------------
// Demographics
// ---------------------------------------------------------------------------

const ageRangeValues = [
  '18-24',
  '25-34',
  '35-44',
  '45-54',
  '55-64',
  '65+',
] as const;

const genderValues = [
  'male',
  'female',
  'diverse',
  'prefer_not_to_say',
] as const;

const educationValues = [
  'no_degree',
  'hauptschule',
  'realschule',
  'abitur',
  'bachelor',
  'master',
  'doctorate',
  'other',
] as const;

const aiChatUsageFrequencyValues = [
  'never',
  'less_than_monthly',
  'several_times_per_month',
  'several_times_per_week',
  'almost_daily',
] as const;

export const demographicsSchema = z.object({
  ageRange: z.enum(ageRangeValues, { error: REQUIRED_SELECT }),
  gender: z.enum(genderValues, { error: REQUIRED_SELECT }),
  education: z.enum(educationValues, { error: REQUIRED_SELECT }),
  politicalInterest: z.number({ error: REQUIRED_RATING }).min(1).max(7),
  aiChatUsageFrequency: z.enum(aiChatUsageFrequencyValues, {
    error: REQUIRED_SELECT,
  }),
  netPromoterScore: z.number({ error: REQUIRED_RATING }).min(0).max(10),
});

export type DemographicsFormValues = z.infer<typeof demographicsSchema>;

// ---------------------------------------------------------------------------
// UEQ-S
// ---------------------------------------------------------------------------

const ueqRating = z.number({ error: REQUIRED_RATING }).min(1).max(7);

export const ueqShortSchema = z.object({
  item1: ueqRating,
  item2: ueqRating,
  item3: ueqRating,
  item4: ueqRating,
  item5: ueqRating,
  item6: ueqRating,
  item7: ueqRating,
  item8: ueqRating,
  qualitativeFeedback,
});

export type UeqShortFormValues = z.infer<typeof ueqShortSchema>;

// ---------------------------------------------------------------------------
// Cognitive Load (Klepsch et al. 2017, 1-7 Likert)
// ---------------------------------------------------------------------------

const cognitiveLoadRating = z.number({ error: REQUIRED_RATING }).min(1).max(7);

export const cognitiveLoadSchema = z.object({
  cl_icl_1: cognitiveLoadRating,
  cl_icl_2: cognitiveLoadRating,
  cl_ecl_1: cognitiveLoadRating,
  cl_ecl_2: cognitiveLoadRating,
  cl_ecl_3: cognitiveLoadRating,
  cl_gcl_1: cognitiveLoadRating,
  cl_gcl_2: cognitiveLoadRating,
  // Embedded attention check. Validated by form, split out at submit so it
  // never lands inside the CL response object that downstream code scores.
  attentionCheck: cognitiveLoadRating,
  qualitativeFeedback,
});

export type CognitiveLoadFormValues = z.infer<typeof cognitiveLoadSchema>;
