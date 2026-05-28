/**
 * Questionnaire types for Cognitive Load (Klepsch et al. 2017) and UEQ-S
 */

// Klepsch, Schmitz & Seufert (2017). Frontiers in Psychology, 8, Article 1997.
// https://doi.org/10.3389/fpsyg.2017.01997
// Naive-rating questionnaire (final version, Table 3).
// 7 items, 7-point Likert. Anchors are direct German translations of the
// original "completely wrong" / "absolutely right".
// Optional GCL* item omitted (no germane-load manipulation between conditions).
// "Lerneinheit" → "Aufgabe" in cl_gcl_2 to match task framing (declared
// adaptation).

export type CognitiveLoadSubscale = 'ICL' | 'ECL' | 'GCL';

export interface CognitiveLoadItem {
  id: string;
  subscale: CognitiveLoadSubscale;
  text: string;
}

export const COGNITIVE_LOAD_ITEMS: readonly CognitiveLoadItem[] = [
  // Intrinsic — manipulation check (should NOT differ between conditions)
  {
    id: 'cl_icl_1',
    subscale: 'ICL',
    text: 'Bei der Aufgabe musste man viele Dinge gleichzeitig im Kopf bearbeiten.',
  },
  {
    id: 'cl_icl_2',
    subscale: 'ICL',
    text: 'Diese Aufgabe war sehr komplex.',
  },

  // Extraneous — primary cognitive-load DV (H4b) and mediator (H4e)
  {
    id: 'cl_ecl_1',
    subscale: 'ECL',
    text: 'Bei dieser Aufgabe ist es mühsam, die wichtigsten Informationen zu erkennen.',
  },
  {
    id: 'cl_ecl_2',
    subscale: 'ECL',
    text: 'Die Darstellung bei dieser Aufgabe ist ungünstig, um wirklich etwas zu lernen.',
  },
  {
    id: 'cl_ecl_3',
    subscale: 'ECL',
    text: 'Bei dieser Aufgabe ist es schwer, die zentralen Inhalte miteinander in Verbindung zu bringen.',
  },

  // Germane — descriptive
  {
    id: 'cl_gcl_1',
    subscale: 'GCL',
    text: 'Ich habe mich angestrengt, mir nicht nur einzelne Dinge zu merken, sondern auch den Gesamtzusammenhang zu verstehen.',
  },
  {
    id: 'cl_gcl_2',
    subscale: 'GCL',
    text: 'Es ging mir beim Bearbeiten der Aufgabe darum, alles richtig zu verstehen.',
  },
] as const;

export const COGNITIVE_LOAD_ANCHORS = {
  low: 'Komplett falsch',
  high: 'Komplett richtig',
  scale: [1, 2, 3, 4, 5, 6, 7] as const,
};

export interface CognitiveLoadResponse {
  cl_icl_1: number;
  cl_icl_2: number;
  cl_ecl_1: number;
  cl_ecl_2: number;
  cl_ecl_3: number;
  cl_gcl_1: number;
  cl_gcl_2: number;
  // Optional free-text comment, collected only in qualitative studies.
  qualitativeFeedback?: string;
}

export interface UeqItem {
  id: number;
  leftAnchor: string;
  rightAnchor: string;
  scale: 'pragmatic' | 'hedonic';
}

export const UEQ_SHORT_ITEMS: UeqItem[] = [
  {
    id: 1,
    leftAnchor: 'behindernd',
    rightAnchor: 'unterstützend',
    scale: 'pragmatic',
  },
  {
    id: 2,
    leftAnchor: 'kompliziert',
    rightAnchor: 'einfach',
    scale: 'pragmatic',
  },
  {
    id: 3,
    leftAnchor: 'ineffizient',
    rightAnchor: 'effizient',
    scale: 'pragmatic',
  },
  {
    id: 4,
    leftAnchor: 'verwirrend',
    rightAnchor: 'übersichtlich',
    scale: 'pragmatic',
  },
  {
    id: 5,
    leftAnchor: 'langweilig',
    rightAnchor: 'spannend',
    scale: 'hedonic',
  },
  {
    id: 6,
    leftAnchor: 'uninteressant',
    rightAnchor: 'interessant',
    scale: 'hedonic',
  },
  {
    id: 7,
    leftAnchor: 'konventionell',
    rightAnchor: 'originell',
    scale: 'hedonic',
  },
  {
    id: 8,
    leftAnchor: 'herkömmlich',
    rightAnchor: 'neuartig',
    scale: 'hedonic',
  },
];

export interface UeqData {
  item1: number; // 1-7
  item2: number;
  item3: number;
  item4: number;
  item5: number;
  item6: number;
  item7: number;
  item8: number;
  itemOrder: number[]; // Randomized order for analysis
  // Optional free-text comment, collected only in qualitative studies.
  qualitativeFeedback?: string;
}

export interface QuestionnaireData {
  cognitiveLoad: CognitiveLoadResponse;
  // Embedded attention check (1-7). Expected value: 2. Stored as a sibling
  // of the scale data so it never pollutes CL subscale scoring.
  attentionCheck: number;
  ueqS: UeqData;
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
}

export interface QuizAnswer {
  questionId: string;
  // 0-2 for substantive options; -1 for the "Weiß ich nicht" UI abstain.
  selectedIndex: number;
  responseTimeMs: number;
}

export interface QuizData {
  isReady: boolean;
  questions: QuizQuestion[];
}

export interface QuizScore {
  totalCorrect: number;
  totalWrong: number;
  totalQuestions: number;
  scorePercentage: number;
  scorePenalty: number;
  attentionCheckPassed: boolean;
}
