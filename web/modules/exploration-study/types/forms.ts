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

export type NewsSource =
  | 'online'
  | 'tv'
  | 'newspaper'
  | 'social_media'
  | 'radio';

/**
 * Meta-Artificial Intelligence Literacy Scale – Short Version (MAILS-Short)
 * Koch, Carolus, et al., 2024
 *
 * 10 items, 11-point self-assessment scale (0 = gar nicht ausgeprägt,
 * 10 = (nahezu) perfekt ausgeprägt).
 */
export interface MailsShortItem {
  /** 1-indexed item number */
  id: number;
  /** Verbatim German item text */
  text: string;
}

export interface MailsShortData {
  item1: number; // 0-10
  item2: number;
  item3: number;
  item4: number;
  item5: number;
  item6: number;
  item7: number;
  item8: number;
  item9: number;
  item10: number;
}

export const MAILS_SHORT_INTRO = `Im Folgenden liest du Beschreibungen verschiedener Fähigkeiten, die man im Umgang mit künstlicher Intelligenz haben kann. Diese Fähigkeiten können stärker oder schwächer ausgeprägt sein. Bitte bewerte dich selbst: Wie stark sind deine Fähigkeiten ausgeprägt?

Ein Wert von 0 bedeutet, dass eine Fähigkeit gar nicht oder kaum ausgeprägt ist. Ein Wert von 10 bedeutet, dass eine Fähigkeit sehr gut oder (nahezu) perfekt ausgeprägt ist.`;

export const MAILS_SHORT_ITEMS: MailsShortItem[] = [
  {
    id: 1,
    text: 'Ich kann erkennen, ob ich es mit einer Anwendung zu tun habe, die auf KI basiert.',
  },
  {
    id: 2,
    text: 'Ich kann neue Anwendungen im Bereich „künstliche Intelligenz" programmieren.',
  },
  {
    id: 3,
    text: 'Obwohl es häufig neue KI-Anwendungen gibt, gelingt es mir, mein Wissen und meine Fähigkeiten aktuell zu halten.',
  },
  {
    id: 4,
    text: 'Ich kann damit umgehen, wenn mich Interaktionen mit KI frustrieren oder ängstigen.',
  },
  {
    id: 5,
    text: 'Ich kann abwägen, welche Konsequenzen die Nutzung von KI für die Gesellschaft hat.',
  },
  {
    id: 6,
    text: 'Ich kann neue KI-Anwendungen designen.',
  },
  {
    id: 7,
    text: 'Ich kann KI sinnvoll einsetzen, um meine Ziele zu erreichen.',
  },
  {
    id: 8,
    text: 'Auch anstrengende und komplizierte Aufgaben bei der Zusammenarbeit mit künstlicher Intelligenz kann ich in der Regel gut lösen.',
  },
  {
    id: 9,
    text: 'Ich kann verhindern, dass KI mich in meinen Entscheidungen beeinflusst.',
  },
  {
    id: 10,
    text: 'Ich kann einschätzen, welche Vor- und Nachteile der Einsatz einer KI mit sich bringt.',
  },
];

export interface LiteracyData {
  mailsShort: MailsShortData;
  newsConsumption: NewsSource[]; // Multiple sources allowed
}

export interface FeedbackData {
  feedback?: string;
}
