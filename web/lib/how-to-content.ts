import { DEFAULT_LOCALE, type Locale } from '@/i18n/locales';
import { HOW_TO_DE } from '@/lib/how-to-content.de';
import { HOW_TO_EN } from '@/lib/how-to-content.en';

/**
 * Every string the how-to content is made of, one module per language.
 *
 * Three surfaces read from here: the /how-to page, its PDF export, and the
 * landing sections (FAQ, data sources and the FAQ JSON-LD). Plain data, no JSX
 * and no 'use client', so server and client components can both import it.
 *
 * The prose is plain text rather than message-catalog rich text because the
 * PDF export prints it as-is; the web surfaces add links and bold by splitting
 * on markers that occur verbatim in every language (domains, e-mail addresses,
 * paths, `wahl.chat`) plus the few language-specific ones in `labels`.
 */

export interface HowToSection {
  subtitle?: string;
  list?: string[];
}

export interface HowToAccordionContent {
  intro?: string;
  paragraphs?: string[];
  list?: string[];
  /** Entries may be `Label: text`; see parseLabeledListItem. */
  orderedList?: string[];
  sections?: HowToSection[];
  origin?: string;
  outro?: string;
}

export interface HowToAccordionItem {
  /** Stable across languages: the page picks its rendering by id. */
  id: string;
  title: string;
  content: HowToAccordionContent;
}

export interface HowToIntroText {
  main: string;
  sources: string;
}

export interface HowToLabels {
  /** Heading above the process steps. */
  processHeading: string;
  /** Heading above the founders' origin story. */
  originHeading: string;
  /**
   * Lead-in for the wahl-o-mat-difference list. Presentational rather than
   * part of the answer text — it introduces the list on both the how-to page
   * and the landing FAQ, and is deliberately not in the answer so the PDF
   * export keeps printing what it prints today.
   */
  wahlOMatListLeadIn: string;
  /** Link text that replaces `/sources` in the data answer's outro. */
  sourcesLinkText: string;
  /**
   * The plus button named in the number-parties answer: `phrase` is how the
   * prose names it, and the page draws the icon followed by `iconSuffix` in
   * its place.
   */
  plusButton: { phrase: string; iconSuffix: string };
  pdfTitle: string;
  pdfFileName: string;
}

export interface HowToContent {
  introText: HowToIntroText;
  processSteps: string[];
  accordionContent: HowToAccordionItem[];
  labels: HowToLabels;
}

const HOW_TO_CONTENT: Record<Locale, HowToContent> = {
  de: HOW_TO_DE,
  en: HOW_TO_EN,
};

export function getHowToContent(locale: Locale): HowToContent {
  return HOW_TO_CONTENT[locale] ?? HOW_TO_CONTENT[DEFAULT_LOCALE];
}

/**
 * Domains named in the data-sources answer that should render as links.
 *
 * The answer text stays plain prose — the PDF export prints it as-is — and
 * the two web surfaces linkify it through this map rather than each
 * hardcoding its own split. Domains read the same in every language.
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
export function getAccordionItem(
  locale: Locale,
  id: string,
): HowToAccordionItem | undefined {
  return getHowToContent(locale).accordionContent.find(
    (item) => item.id === id,
  );
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

export function getLandingFaqItems(locale: Locale): HowToAccordionItem[] {
  return LANDING_FAQ_IDS.flatMap((id) => {
    const item = getAccordionItem(locale, id);
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
