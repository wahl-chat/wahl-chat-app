import type { FeedLocale } from '@/lib/firebase/firebase.types';

/** The feed's own chrome in each language. The items' texts come translated
 * from the backend; only the labels around them live here. The rest of the
 * site, and the chat the feed hands over to, stay German. */

export const FEED_LOCALES: readonly FeedLocale[] = ['de', 'en'];
export const DEFAULT_LOCALE: FeedLocale = 'de';
export const LOCALE_PARAM = 'lang';
export const LOCALE_STORAGE_KEY = 'wahlchat-feed-lang';

export function parseLocaleParam(
  value: string | string[] | null | undefined,
): FeedLocale | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  return FEED_LOCALES.find((l) => l === raw?.toLowerCase());
}

/** Region-qualified, so dates read like the language's own news sites. */
export function intlLocale(locale: FeedLocale): string {
  return locale === 'en' ? 'en-GB' : 'de-DE';
}

const de = {
  language: 'Sprache',
  interesting: 'Interessant?',
  interestYes: 'Interessant',
  interestNo: 'Nicht interessant',
  more: 'Mehr anzeigen',
  moreAbout: (title: string) => `Mehr anzeigen: ${title}`,
  share: 'Teilen',
  linkCopied: 'Link kopiert',
  passed: 'Angenommen',
  rejected: 'Abgelehnt',
  topicOfDay: 'Thema des Tages',
  matchingVote: 'Passende Abstimmung',
  plenarySitting: 'Plenarsitzung',
  vote: 'Abstimmung',
  protocol: (id: string) => `Protokoll ${id}`,
  heatOutOf: (heat: number, max: number) => `Hitzigkeit ${heat} von ${max}`,
  heatShort: (heat: number) => `Hitzigkeit ${heat}/5`,
  empty: 'Noch keine Inhalte zu deiner Auswahl. Schau bald wieder vorbei.',
  backToFeed: 'Zurück zum Feed',
  inShort: 'Kurz gesagt',
  whoSaysWhat: 'Wer sagt was',
  source: (id: string) => `Quelle: Plenarprotokoll ${id}`,
  whatAbout: 'Worum ging es?',
  howGroupsVoted: 'So haben die Fraktionen gestimmt',
  originalTitle: (title: string) => `Originaltitel: ${title}`,
  voteOnAw: 'Abstimmung auf abgeordnetenwatch.de',
  askMore: 'Mehr wissen? Frag nach.',
  askVote: 'Frag zu dieser Abstimmung …',
  askDebate: 'Frag zu dieser Debatte …',
  seat: { yes: 'Ja', no: 'Nein', abstain: 'Enthalten', absent: 'Abwesend' },
  yesNo: 'Ja : Nein',
  voteResult: (yes: number, no: number, abstain: number, absent: number) =>
    `Abstimmungsergebnis: ${yes} Ja, ${no} Nein, ${abstain} Enthaltungen, ${absent} abwesend.`,
  seats: (name: string, seats: number) => `${name}: ${seats} Sitze`,
  chooseParliament: 'Parlament wählen',
  chooseParliamentChosen: (names: string) =>
    `Parlament wählen, gewählt: ${names}`,
  chosenCount: (n: number) => `${n} gewählt`,
  defaultChoice: 'Standard',
  landtage: 'Landtage',
  soon: 'bald',
  reset: 'Zurücksetzen',
  pickOne: 'Mindestens eins wählen',
  done: 'Fertig',
  topics: 'Themen',
  allTopics: 'Alle Themen',
  playSpeech: 'Rede abspielen',
  playAudio: 'Audio abspielen',
  from: (speaker: string, time: string) => `${speaker} · ab ${time}`,
};

export type FeedStrings = typeof de;

const en: FeedStrings = {
  language: 'Language',
  interesting: 'Interesting?',
  interestYes: 'Interesting',
  interestNo: 'Not interesting',
  more: 'Show more',
  moreAbout: (title) => `Show more: ${title}`,
  share: 'Share',
  linkCopied: 'Link copied',
  passed: 'Passed',
  rejected: 'Rejected',
  topicOfDay: 'Topic of the day',
  matchingVote: 'Related vote',
  plenarySitting: 'Plenary sitting',
  vote: 'Vote',
  protocol: (id) => `Plenary record ${id}`,
  heatOutOf: (heat, max) => `Intensity ${heat} of ${max}`,
  heatShort: (heat) => `Intensity ${heat}/5`,
  empty: 'Nothing for your selection yet. Check back soon.',
  backToFeed: 'Back to the feed',
  inShort: 'In short',
  whoSaysWhat: 'Who said what',
  source: (id) => `Source: plenary record ${id} (German)`,
  whatAbout: 'What was it about?',
  howGroupsVoted: 'How the parliamentary groups voted',
  originalTitle: (title) => `Original German title: ${title}`,
  voteOnAw: 'The vote on abgeordnetenwatch.de (German)',
  askMore: 'Want to know more? Ask.',
  askVote: 'Ask about this vote …',
  askDebate: 'Ask about this debate …',
  seat: { yes: 'Yes', no: 'No', abstain: 'Abstained', absent: 'Absent' },
  yesNo: 'Yes : No',
  voteResult: (yes, no, abstain, absent) =>
    `Result: ${yes} yes, ${no} no, ${abstain} abstentions, ${absent} absent.`,
  seats: (name, seats) => `${name}: ${seats} seats`,
  chooseParliament: 'Choose parliament',
  chooseParliamentChosen: (names) => `Choose parliament, selected: ${names}`,
  chosenCount: (n) => `${n} selected`,
  defaultChoice: 'Default',
  landtage: 'State parliaments',
  soon: 'soon',
  reset: 'Reset',
  pickOne: 'Pick at least one',
  done: 'Done',
  topics: 'Topics',
  allTopics: 'All topics',
  playSpeech: 'Play speech',
  playAudio: 'Play audio',
  from: (speaker, time) => `${speaker} · from ${time}`,
};

export const FEED_STRINGS: Record<FeedLocale, FeedStrings> = { de, en };
