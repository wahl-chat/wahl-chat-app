import { MAX_SELECTABLE_PARTIES } from '@/lib/constants';
import type {
  HowToAccordionContent,
  HowToAccordionItem,
  HowToIntroText,
} from '@/lib/how-to-pdf-export';

/**
 * Every string the how-to content is made of, in one place.
 *
 * Moved out of components/how-to.tsx so the landing page can show the same
 * copy without a second phrasing of it. Three surfaces read from here: the
 * /how-to page, its PDF export, and the landing sections. Plain data, no JSX
 * and no 'use client', so server and client components can both import it.
 */

// Content configuration - single source of truth
const PARTY_SPECIFIC_QUESTIONS = [
  'Was ist die Position der SPD zu Klimaschutz?',
  'Wie steht die AfD zur Schuldenbremse?',
  'Wie will die CDU/CSU Bürokratie reduzieren?',
  'Wie wollen die Grünen die Digitalisierung vorantreiben?',
  'Wie wollen die FDP und die Linke die Arbeitszeitreform umsetzen?',
  'Wie wollen Volt und die FDP europäische Zusammenarbeit verbessern?',
];

const COMPARE_QUESTIONS = [
  'Wie unterscheiden sich die Parteien im Kampf gegen den Klimawandel?',
  'Wie unterscheiden sich die Positionen der CDU/CSU und der SPD zum Thema Schuldenbremse?',
  'Vergleiche die Positionen der FDP und AfD zum Thema Migration.',
];

const GENERAL_QUESTIONS = [
  'Wie kann ich Briefwahl beantragen?',
  'Wer steht hinter wahl.chat?',
  'Wie funktioniert Briefwahl?',
];

export const INTRO_TEXT: HowToIntroText = {
  main: 'wahl.chat ist ein interaktives KI-Tool, das dir hilft, dich über die Positionen und Pläne der Parteien zu informieren. Du kannst dem KI-Assistenten Fragen zu verschiedenen politischen Themen stellen, und er liefert dir neutrale Antworten basierend auf den Wahlprogrammen und weiteren Veröffentlichungen der Parteien.',
  sources:
    'Alle Antworten sind mit den entsprechenden Quellen versehen und nutzen für die ausgewählte Wahl relevante Dokumente.',
};

export const PROCESS_STEPS: string[] = [
  'Du stellst eine Frage',
  'wahl.chat durchsucht relevante Dokumente wie Wahl- und Grundsatzprogramme, um die passenden Informationen zu finden.',
  'Die relevanten Informationen werden dann genutzt, um eine verständliche und quellenbasierte Antwort zu generieren.',
  'Du kannst dir nun die Position der Partei einordnen lassen, indem du auf den Knopf unter der Antwort klickst.',
  'Falls uns das Abstimmungsverhalten der Partei vorliegt, kannst du die Antwort auch mit passenden Gesetzesvorschlägen abgleichen.',
];

export const ACCORDION_CONTENT: HowToAccordionItem[] = [
  {
    id: 'questions',
    title: 'Welche Fragen kann ich stellen?',
    content: {
      intro:
        'Grundsätzlich kannst du alle Fragen stellen, die du zu den Positionen der Parteien hast. Falls du mehrere Parteien miteinander vergleichen willst, kannst du sie entweder dem Chat hinzufügen oder sie einfach in der Frage erwähnen. Des Weiteren kannst du auch Fragen zu generellen Themen wie dem Ablauf einer Wahl stellen.',
      sections: [
        {
          subtitle: 'Beispiele für Partei-spezifische Fragen:',
          list: PARTY_SPECIFIC_QUESTIONS,
        },
        {
          subtitle: 'Beispiele für vergleichende Fragen:',
          list: COMPARE_QUESTIONS,
        },
        {
          subtitle: 'Beispiele für allgemeine Fragen:',
          list: GENERAL_QUESTIONS,
        },
      ],
    },
  },
  {
    id: 'elections-supported',
    title: 'Welche Wahlen werden unterstützt?',
    content: {
      intro: 'Aktuell unterstützen wir folgende Wahlen:',
      list: [
        'Landtagswahl Baden-Württemberg - 8. März 2026',
        'Landtagswahl Rheinland-Pfalz - 22. März 2026',
        'Kommunalwahl München - 8. März 2026',
      ],
      outro:
        'Zusätzlich können im Bereich **Bundesebene** allgemeine Informationen über die Positionen der Parteien beantwortet werden.',
    },
  },
  {
    id: 'number-parties',
    title: 'Mit wie vielen Parteien kann ich chatten?',
    content: {
      paragraphs: [
        `Du kannst den Chat mit bis zu ${MAX_SELECTABLE_PARTIES} Parteien gleichzeitig starten, hast aber die Möglichkeit, während des Chattens noch weitere Parteien anzusprechen.`,
        'Des Weiteren kannst du ganz einfach durch den Plus-Knopf über dem Textfeld weitere Parteien zum Chat hinzufügen oder auch wieder entfernen.',
      ],
    },
  },
  {
    id: 'position',
    title: 'Position einordnen',
    content: {
      paragraphs: [
        'Wenn du diesen Knopf unter einer der Nachrichten klickst, wird die Position der Nachricht eingeordnet. Dabei werden die folgenden Kriterien berücksichtigt: Machbarkeit, kurzfristige und langfristige Effekte.',
        'Hierbei nutzen wir aktuelle Informationen und Quellen aus dem Internet, die uns von Perplexity.ai zur Verfügung gestellt werden.',
      ],
    },
  },
  {
    id: 'voting-behavior-analyze',
    title: 'Abstimmungsverhalten analysieren',
    content: {
      paragraphs: [
        'Mit dieser Funktion kannst du die Antwort einer Partei im Kontext vergangener Abstimmungen im Bundestag einordnen. Darüber hinaus kannst du durch einen Klick auf "Abstimmungen anzeigen" detaillierte Informationen zu den relevanten Abstimmungen anzeigen und visualisieren lassen. Dies ermöglicht es, die Pläne einer Partei laut ihrem Programm anhand ihres realpolitischen Verhaltens einzuordnen.',
      ],
    },
  },
  {
    id: 'data',
    title: 'Welche Daten werden verwendet?',
    content: {
      intro:
        'Um fundierte und quellenbasierte Antworten zu liefern, verwendet wahl.chat eine Vielzahl von Datenquellen:',
      orderedList: [
        'Parteidokumente: Als Datenbasis werden Grundsatzprogramme, Wahlprogramme, Positionspapiere und weitere von den Parteien stammende Dokumente herangezogen, um ein umfassendes Bild der Parteipositionen zu erhalten.',
        'Plenarprotokolle: Was die Parteien im Parlament tatsächlich gesagt haben, entnehmen wir den Plenarprotokollen des Bundestages, die über das Dokumentations- und Informationssystem für Parlamentsmaterialien (DIP) unter dip.bundestag.de bereitgestellt werden.',
        'Abstimmungsverhalten im Bundestag: Für die Analyse des Abstimmungsverhaltens nutzen wir Daten zu Bundestagsabstimmungen, die über abgeordnetenwatch.de bereitgestellt werden. Diese Daten ermöglichen es, Parteipositionen mit ihrem realpolitischen Verhalten abzugleichen.',
        'Internetquellen für die Einordnung von Positionen: Für die differenzierte Einordnung von Positionen nutzt wahl.chat den Dienst Perplexity.ai, der hochwertige Internetquellen wie Nachrichtenseiten verwendet.',
      ],
      outro:
        'Wir haben alle Quellen, die wahl.chat nutzt, auf unserer Webseite unter /sources aufgelistet.',
    },
  },
  {
    id: 'guidelines',
    title: 'Welchen Leitlinien folgt wahl.chat in seinen Antworten?',
    content: {
      intro: 'Folgende Leitlinien gelten für die Antworten in den Chats:',
      orderedList: [
        'Quellenbasiert: Die Antworten sollen auf den relevanten Aussagen aus den bereitgestellten Programmauszügen beruhen.',
        'Neutralität: Parteipositionen sollen neutral und ohne Wertung wiedergegeben werden.',
        'Transparenz: Zu jeder Aussage sollen direkt die relevanten Quellen verlinkt werden, um eine detaillierte Betrachtung und Überprüfung des Inhalts zu ermöglichen.',
      ],
    },
  },
  {
    id: 'party-selection',
    title: 'Nach welchen Kriterien werden die Parteien ausgewählt?',
    content: {
      paragraphs: [
        'Die ursprüngliche Auswahl der Parteien für den bundesweiten Kontext erfolgte vor der Bundestagswahl 2025 und orientierte sich an der Veröffentlichung ihrer Wahlprogramme. Wir wollen nun nach und nach auch für die anderen unterstützten Wahlen eine möglichst vollständige Parteienauswahl anbieten und freuen uns dafür über deine Mithilfe.',
        'Solltest du eine Partei vermissen, schreibe uns gerne eine E-Mail mit ihrem Wahl- oder Grundsatzprogramm oder anderen relevanten Dokumenten als PDF an info@wahl.chat, und wir werden sie so schnell wie möglich ergänzen.',
      ],
    },
  },
  {
    id: 'about-founders',
    title: 'Wer steckt hinter wahl.chat und wie kam es dazu?',
    content: {
      intro:
        'Gegründet wurde wahl.chat von fünf Studierenden der LMU, TUM und University of Cambridge. Sie kamen für ein gemeinsames Forschungsprojekt zum Thema KI in Cambridge zusammen und haben mittlerweile ihre Studien abgeschlossen.',
      sections: [
        {
          subtitle: 'Die Gründungsmitglieder und ihre heutigen Positionen:',
          list: [
            'Sebastian Maier - Doktorand an der LMU München',
            'Anton Wyrowski - Entwickler bei Perplexity',
            'Michel Schimpf - Doktorand an der University of Cambridge',
            'Robin Frasch - Doktorand an der Uni Hamburg',
            'Roman Mayr - Entwickler bei Knowunity',
          ],
        },
      ],
      origin:
        'Ende November 2024 saß das Team in Cambridge beim Mittagessen zusammen. Beim Gespräch kam das Thema auf, dass der Opa des Deutschrappers Ski Aggu am Wahl-O-Mat gearbeitet hat. Es kam die Idee auf, einen neuen Wahl-O-Mat mit KI für die Einordnung der eigenen Meinung zu den Wahlkampfthemen zu bauen. Doch wäre es nicht noch spannender, den Spieß umzudrehen und mit den für einen selbst relevanten Parteien ausführlicher zu chatten? Und nicht nur eine Aussage zu vorgeschriebenen Thesen zu erhalten, sondern ganz individuelle Anliegen klären zu können? Und so war Ende November 2024 die Idee für wahl.chat geboren.',
      outro: 'Weitere Infos können auch unter /about-us nachgelesen werden.',
    },
  },
  {
    id: 'wahl-o-mat-difference',
    title: 'Wie unterscheidet sich wahl.chat vom Wahl-O-Mat?',
    content: {
      intro:
        'Beim Wahl-O-Mat entscheidet man zu vorgegebenen Thesen "finde ich gut", "hier bin ich neutral", oder "hier bin ich dagegen". wahl.chat ist dagegen wie ein offenes Gespräch, um besser zu verstehen, was die Parteien fordern.',
      orderedList: [
        'Fragen zu den Themen stellen, die einen selbst am meisten interessieren.',
        'Ins Detail gehen, um die Begriffe, Vorstellungen und Pläne der Parteien genau zu verstehen.',
        'Positionen kritisch einordnen, um Für- und Wider abzuwägen.',
      ],
    },
  },
  {
    id: 'data-privacy',
    title: 'Sind meine Daten bei der Verwendung von wahl.chat sicher?',
    content: {
      paragraphs: [
        'Ja, wahl.chat kommt ohne Cookies und ohne die Erfassung persönlicher Daten aus. Lediglich die Chats werden anonymisiert gespeichert. Durch Zugriffskontrollen verhindern wir unbefugten Zugriff auf die Chats anderer.',
        'Man sollte dennoch vermeiden, sensible persönliche Daten in die Chats zu schreiben.',
      ],
    },
  },
  {
    id: 'usage-statistics',
    title: 'Werden Nutzungsstatistiken erfasst?',
    content: {
      paragraphs: [
        'Um wahl.chat kontinuierlich zu verbessern, werden die Webseitenanfragen und die anonymisierten Chatverläufe verwendet, um aggregierte Statistiken, wie die Anzahl der beantworteten Fragen oder die Parteien, mit denen am meisten gechattet wird, zu bestimmen.',
        'Da wir die Entwicklung von wahl.chat wissenschaftlich begleiten, werden wir von Zeit zu Zeit unseren Nutzerinnen und Nutzern die Möglichkeit geben, an Studien teilzunehmen. Diese werden 100% freiwillig sein und eine Ablehnung wird keinen Einfluss auf die weitere Verwendbarkeit von wahl.chat haben. In diesen Studien werden wir die anonymisierten Nutzungsstatistiken verwenden, um die Wirkung von wahl.chat zu analysieren und den positiven Impact weiter zu verbessern.',
      ],
    },
  },
  {
    id: 'learning',
    title: 'Lernt wahl.chat mit der Zeit selbstständig dazu?',
    content: {
      paragraphs: [
        'Nein, die Chatverläufe werden nicht für weiteres Training der LLMs verwendet. Wir arbeiten allerdings kontinuierlich daran, die Qualität der Antworten zu verbessern, halten unsere Datenbasis stets aktuell und planen, weitere relevante Dokumente zur Antwortgenerierung hinzuzufügen.',
      ],
    },
  },
  {
    id: 'contribute',
    title: 'Wie kann ich zu wahl.chat beitragen?',
    content: {
      paragraphs: [
        'wahl.chat ist ein Open-Source-Projekt und unser Code ist öffentlich auf GitHub einsehbar unter https://github.com/wahl-chat.',
        'Wir freuen uns über Unterstützung und sind immer auf der Suche nach Freiwilligen, die mit uns gemeinsam die Demokratie stärken möchten. Wenn du Interesse hast, dich einzubringen, kontaktiere uns gerne unter info@wahl.chat.',
      ],
    },
  },
];

/**
 * Lead-in for the wahl-o-mat-difference list. Presentational rather than part
 * of the answer text — it introduces the list on both the how-to page and the
 * landing FAQ, and is deliberately not in ACCORDION_CONTENT so the PDF export
 * keeps printing what it prints today.
 */
export const WAHL_O_MAT_LIST_LEAD_IN = 'Bei wahl.chat kann man:';

/**
 * Domains named in the data-sources answer that should render as links.
 *
 * The answer text stays plain prose in ACCORDION_CONTENT — the PDF export
 * prints it as-is — and the two web surfaces linkify it through this map
 * rather than each hardcoding its own split.
 */
const SOURCE_DOMAIN_LINKS: Record<string, string> = {
  'dip.bundestag.de': 'https://dip.bundestag.de',
  'abgeordnetenwatch.de': 'https://www.abgeordnetenwatch.de',
};

/**
 * Splits prose into plain and linkable segments, so a caller can render each
 * with its own markup without knowing which domains are linkable.
 */
export function splitOnSourceDomains(
  text: string,
): { text: string; href?: string }[] {
  const domains = Object.keys(SOURCE_DOMAIN_LINKS);
  const pattern = new RegExp(
    `(${domains.map((d) => d.replace(/\./g, '\\.')).join('|')})`,
  );

  return text
    .split(pattern)
    .filter((part) => part.length > 0)
    .map((part) => ({ text: part, href: SOURCE_DOMAIN_LINKS[part] }));
}

/** Look up one entry by id. Undefined if the id no longer exists. */
export function getAccordionItem(id: string): HowToAccordionItem | undefined {
  return ACCORDION_CONTENT.find((item) => item.id === id);
}

/**
 * The subset shown on the landing page, in this order rather than the how-to
 * page's. It leads with the Wahl-O-Mat differentiator because that is the
 * question a first-time visitor actually arrives with.
 *
 * Deliberately excludes 'elections-supported': it hardcodes three elections
 * while Firestore has seven, and the landing page renders the real list.
 * 'data' is excluded too — it carries the data-sources section instead.
 */
const LANDING_FAQ_IDS = [
  'wahl-o-mat-difference',
  'data-privacy',
  'guidelines',
  'party-selection',
  'contribute',
];

export function getLandingFaqItems(): HowToAccordionItem[] {
  return LANDING_FAQ_IDS.flatMap((id) => {
    const item = getAccordionItem(id);
    return item ? [item] : [];
  });
}

/**
 * The visible text of an answer, flattened to one string.
 *
 * FAQPage structured data must match what the page actually shows, so the
 * markup and the JSON-LD both derive from this rather than from two separate
 * readings of the content shape.
 */
export function flattenAccordionContentToText(
  content: HowToAccordionContent,
): string {
  return [
    content.intro,
    ...(content.orderedList ?? []),
    ...(content.list ?? []),
    ...(content.sections ?? []).flatMap((section) => [
      section.subtitle,
      ...(section.list ?? []),
    ]),
    ...(content.paragraphs ?? []),
    content.origin,
    content.outro,
  ]
    .filter(Boolean)
    .join(' ');
}

/**
 * Splits "Parteidokumente: Als Datenbasis werden..." into its bold label and
 * the rest. The how-to page and the landing page's data-sources cards present
 * these entries differently but must not each own a copy of the parsing.
 */
export function parseLabeledListItem(item: string): {
  label: string;
  text: string;
} {
  const parts = item.split(':');
  return { label: parts[0], text: parts.slice(1).join(':').trim() };
}
