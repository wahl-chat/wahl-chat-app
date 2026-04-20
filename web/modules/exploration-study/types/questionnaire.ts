/**
 * Questionnaire types for NASA-TLX and UEQ-S
 */

export interface NasaTlxData {
  mentalDemand: number; // 1-21
  physicalDemand: number; // 1-21
  temporalDemand: number; // 1-21
  performance: number; // 1-21
  effort: number; // 1-21
  frustration: number; // 1-21
}

export interface NasaTlxItem {
  key: keyof NasaTlxData;
  label: string;
  description: string;
  lowAnchor: string;
  highAnchor: string;
}

export const NASA_TLX_ITEMS: NasaTlxItem[] = [
  {
    key: 'mentalDemand',
    label: 'Geistige Anforderung',
    description:
      'Wie viel geistige Anstrengung war erforderlich (z.B. Denken, Entscheiden, Erinnern)?',
    lowAnchor: 'Sehr gering',
    highAnchor: 'Sehr hoch',
  },
  {
    key: 'physicalDemand',
    label: 'Körperliche Anforderung',
    description:
      'Wie viel körperliche Aktivität war erforderlich (z.B. Klicken, Scrollen, Tippen)?',
    lowAnchor: 'Sehr gering',
    highAnchor: 'Sehr hoch',
  },
  {
    key: 'temporalDemand',
    label: 'Zeitliche Anforderung',
    description:
      'Wie viel Zeitdruck hast du aufgrund der Geschwindigkeit der Aufgaben empfunden?',
    lowAnchor: 'Sehr gering',
    highAnchor: 'Sehr hoch',
  },
  {
    key: 'performance',
    label: 'Leistung',
    description:
      'Wie erfolgreich warst du deiner Meinung nach bei der Erreichung der Aufgabenziele?',
    lowAnchor: 'Sehr schlecht',
    highAnchor: 'Sehr gut',
  },
  {
    key: 'effort',
    label: 'Anstrengung',
    description:
      'Wie hart musstest du arbeiten, um dein Leistungsniveau zu erreichen?',
    lowAnchor: 'Sehr gering',
    highAnchor: 'Sehr hoch',
  },
  {
    key: 'frustration',
    label: 'Frustration',
    description:
      'Wie unsicher, entmutigt, irritiert, gestresst oder verärgert hast du dich gefühlt?',
    lowAnchor: 'Sehr gering',
    highAnchor: 'Sehr hoch',
  },
];

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
}

export interface ManipulationChecksData {
  depth: number; // 1-5 Likert
  clarity: number; // 1-5 Likert
  taskClarity: number; // 1-5 Likert
  technical: number; // 1-5 Likert
}

export interface ManipulationCheckItem {
  key: keyof ManipulationChecksData;
  label: string;
}

export const MANIPULATION_CHECK_ITEMS: ManipulationCheckItem[] = [
  {
    key: 'depth',
    label: 'Die Informationen waren ausreichend detailliert.',
  },
  {
    key: 'clarity',
    label: 'Die Informationen waren verständlich dargestellt.',
  },
  {
    key: 'taskClarity',
    label: 'Mir war klar, was ich tun sollte.',
  },
  {
    key: 'technical',
    label: 'Das System funktionierte ohne technische Probleme.',
  },
];

export interface QuestionnaireData {
  nasaTlx: NasaTlxData;
  ueqS: UeqData;
  manipulationChecks: ManipulationChecksData;
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correctIndex: number;
  party: string;
}

export interface QuizAnswer {
  questionId: string;
  selectedIndex: number;
  responseTimeMs: number;
}

export interface QuizData {
  isReady: boolean;
  questions: QuizQuestion[];
}
