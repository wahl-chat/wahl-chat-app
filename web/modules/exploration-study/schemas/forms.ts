import { z } from 'zod';

const REQUIRED_SELECT = 'Bitte treffe eine Auswahl.';
const REQUIRED_RATING = 'Bitte wähle einen Wert aus.';

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

export const demographicsSchema = z.object({
  ageRange: z.enum(ageRangeValues, { error: REQUIRED_SELECT }),
  gender: z.enum(genderValues, { error: REQUIRED_SELECT }),
  education: z.enum(educationValues, { error: REQUIRED_SELECT }),
  politicalInterest: z.number().min(1).max(7),
});

export type DemographicsFormValues = z.infer<typeof demographicsSchema>;

// ---------------------------------------------------------------------------
// Literacy (MAILS-Short, trimmed to 4 items)
// ---------------------------------------------------------------------------

const mailsRating = z.number({ error: REQUIRED_RATING }).min(0).max(10);

export const literacySchema = z.object({
  mailsShort: z.object({
    item1: mailsRating,
    item5: mailsRating,
    item7: mailsRating,
    item10: mailsRating,
  }),
});

export type LiteracyFormValues = z.infer<typeof literacySchema>;

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
});

export type CognitiveLoadFormValues = z.infer<typeof cognitiveLoadSchema>;

// ---------------------------------------------------------------------------
// Manipulation checks (1-5 Likert)
// ---------------------------------------------------------------------------

const manipulationRating = z.number({ error: REQUIRED_RATING }).min(1).max(5);

export const manipulationChecksSchema = z.object({
  depth: manipulationRating,
  clarity: manipulationRating,
  taskClarity: manipulationRating,
  technical: manipulationRating,
});

export type ManipulationChecksFormValues = z.infer<
  typeof manipulationChecksSchema
>;
