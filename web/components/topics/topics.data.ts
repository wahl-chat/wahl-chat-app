import type { Question } from './topic-question-card';

export type Topic = keyof typeof TOPIC_TITLES;

export const TOPIC_TITLES = {
  economy_finance: {
    title: 'Wirtschaft und Finanzen',
    normal: 'bg-blue-500/20 text-blue-500 border-blue-500/30',
    hover: 'hover:bg-blue-500/40 hover:text-blue-600 hover:border-blue-500/40',
    active:
      'bg-blue-500 text-white border-blue-700 hover:bg-blue-500/80 hover:text-white hover:border-blue-700',
  },
  social_labor: {
    title: 'Soziales und Arbeit',
    normal: 'bg-green-500/20 text-green-500 border-green-500/30',
    hover:
      'hover:bg-green-500/40 hover:text-green-600 hover:border-green-500/40',
    active:
      'bg-green-500 text-white border-green-700 hover:bg-green-500/80 hover:text-white hover:border-green-700',
  },
  education_research: {
    title: 'Bildung und Forschung',
    normal: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
    hover:
      'hover:bg-yellow-500/40 hover:text-yellow-600 hover:border-yellow-500/40',
    active:
      'bg-yellow-500 text-black border-yellow-700 hover:bg-yellow-500/80 hover:text-black hover:border-yellow-700',
  },
  climate_environment: {
    title: 'Klimaschutz und Umwelt',
    normal: 'bg-green-700/20 text-green-700 border-green-700/30',
    hover:
      'hover:bg-green-700/40 hover:text-green-800 hover:border-green-700/40',
    active:
      'bg-green-700 text-white border-green-900 hover:bg-green-700/80 hover:text-white hover:border-green-900',
  },
  health_care: {
    title: 'Gesundheit und Pflege',
    normal: 'bg-red-500/20 text-red-500 border-red-500/30',
    hover: 'hover:bg-red-500/40 hover:text-red-600 hover:border-red-500/40',
    active:
      'bg-red-500 text-white border-red-700 hover:bg-red-500/80 hover:text-white hover:border-red-700',
  },
  digitalization_tech: {
    title: 'Digitalisierung und Technologie',
    normal: 'bg-indigo-500/20 text-indigo-500 border-indigo-500/30',
    hover:
      'hover:bg-indigo-500/40 hover:text-indigo-600 hover:border-indigo-500/40',
    active:
      'bg-indigo-500 text-white border-indigo-700 hover:bg-indigo-500/80 hover:text-white hover:border-indigo-700',
  },
  migration_integration: {
    title: 'Migration und Integration',
    normal: 'bg-orange-500/20 text-orange-500 border-orange-500/30',
    hover:
      'hover:bg-orange-500/40 hover:text-orange-600 hover:border-orange-500/40',
    active:
      'bg-orange-500 text-black border-orange-700 hover:bg-orange-500/80 hover:text-black hover:border-orange-700',
  },
  security_justice: {
    title: 'Innere Sicherheit und Justiz',
    normal:
      'bg-gray-700/20 text-gray-700 border-gray-700/30 dark:bg-gray-300/20 dark:text-gray-300 dark:border-gray-300/30',
    hover:
      'hover:bg-gray-700/40 hover:text-gray-800 hover:border-gray-700/40 dark:hover:bg-gray-300/30 dark:hover:text-gray-400 dark:hover:border-gray-300/40',
    active:
      'bg-gray-700 text-white border-gray-900 dark:bg-gray-300 dark:text-black dark:border-gray-500 hover:bg-gray-700/80 hover:text-white hover:border-gray-900 dark:hover:bg-gray-300/80 dark:hover:text-black dark:hover:border-gray-500',
  },
  foreign_policy_europe: {
    title: 'Außenpolitik und Europa',
    normal: 'bg-purple-500/20 text-purple-500 border-purple-500/30',
    hover:
      'hover:bg-purple-500/40 hover:text-purple-600 hover:border-purple-500/40',
    active:
      'bg-purple-500 text-white border-purple-700 hover:bg-purple-500/80 hover:text-white hover:border-purple-700',
  },
  transport_infrastructure: {
    title: 'Verkehr und Infrastruktur',
    normal: 'bg-blue-700/20 text-blue-700 border-blue-700/30',
    hover: 'hover:bg-blue-700/40 hover:text-blue-800 hover:border-blue-700/40',
    active:
      'bg-blue-700 text-white border-blue-900 hover:bg-blue-700/80 hover:text-white hover:border-blue-900',
  },
  housing_rent: {
    title: 'Wohnungsbau und Mieten',
    normal: 'bg-teal-500/20 text-teal-500 border-teal-500/30',
    hover: 'hover:bg-teal-500/40 hover:text-teal-600 hover:border-teal-500/40',
    active:
      'bg-teal-500 text-white border-teal-700 hover:bg-teal-500/80 hover:text-white hover:border-teal-700',
  },
};

export const topics: Question[] = [
  // Wirtschaft und Finanzen
  {
    id: 'q1',
    question: 'Wie wollen die Parteien das Wirtschaftswachstum fördern?',
    title: 'Wirtschaft und Finanzen',
    topic: 'economy_finance',
  },
  {
    id: 'q2',
    question:
      'Welche Maßnahmen gibt es zur Reduzierung der Staatsverschuldung?',
    title: 'Wirtschaft und Finanzen',
    topic: 'economy_finance',
  },
  {
    id: 'q3',
    question:
      'Wie können kleine Unternehmen und Start-ups besser unterstützt werden?',
    title: 'Wirtschaft und Finanzen',
    topic: 'economy_finance',
  },
  {
    id: 'q4',
    question:
      'Welche Rolle sollte der Staat in der Wirtschaftsregulierung spielen?',
    title: 'Wirtschaft und Finanzen',
    topic: 'economy_finance',
  },
  {
    id: 'q5',
    question: 'Wie kann wirtschaftliche Ungleichheit verringert werden?',
    title: 'Wirtschaft und Finanzen',
    topic: 'economy_finance',
  },

  // Soziales und Arbeit
  {
    id: 'q6',
    question: 'Wie wollen die Parteien die Arbeitsbedingungen verbessern?',
    title: 'Soziales und Arbeit',
    topic: 'social_labor',
  },
  {
    id: 'q7',
    question: 'Welche Reformen sind für das Rentensystem geplant?',
    title: 'Soziales und Arbeit',
    topic: 'social_labor',
  },
  {
    id: 'q8',
    question: 'Wie kann soziale Ungleichheit verringert werden?',
    title: 'Soziales und Arbeit',
    topic: 'social_labor',
  },
  {
    id: 'q9',
    question: 'Welche Maßnahmen gibt es zur Unterstützung von Arbeitslosen?',
    title: 'Soziales und Arbeit',
    topic: 'social_labor',
  },
  {
    id: 'q10',
    question: 'Wie sollten soziale Sicherungssysteme verbessert werden?',
    title: 'Soziales und Arbeit',
    topic: 'social_labor',
  },

  // Bildung und Forschung
  {
    id: 'q11',
    question: 'Wie wollen die Parteien das Bildungssystem verbessern?',
    title: 'Bildung und Forschung',
    topic: 'education_research',
  },
  {
    id: 'q12',
    question:
      'Welche Maßnahmen sind für eine bessere digitale Bildung geplant?',
    title: 'Bildung und Forschung',
    topic: 'education_research',
  },
  {
    id: 'q13',
    question: 'Wie können Universitäten für alle zugänglicher gemacht werden?',
    title: 'Bildung und Forschung',
    topic: 'education_research',
  },
  {
    id: 'q14',
    question: 'Wie sollte Forschung und Innovation gefördert werden?',
    title: 'Bildung und Forschung',
    topic: 'education_research',
  },
  {
    id: 'q15',
    question: 'Welche Rolle spielt lebenslanges Lernen in der Bildungspolitik?',
    title: 'Bildung und Forschung',
    topic: 'education_research',
  },

  // Klimaschutz und Umwelt
  {
    id: 'q16',
    question: 'Welche Maßnahmen gibt es zur Erreichung der Klimaziele?',
    title: 'Klimaschutz und Umwelt',
    topic: 'climate_environment',
  },
  {
    id: 'q17',
    question: 'Wie soll der Ausbau erneuerbarer Energien beschleunigt werden?',
    title: 'Klimaschutz und Umwelt',
    topic: 'climate_environment',
  },
  {
    id: 'q18',
    question:
      'Wie kann der öffentliche Nahverkehr umweltfreundlicher gestaltet werden?',
    title: 'Klimaschutz und Umwelt',
    topic: 'climate_environment',
  },
  {
    id: 'q19',
    question:
      'Welche politischen Maßnahmen gibt es zur Förderung nachhaltiger Landwirtschaft?',
    title: 'Klimaschutz und Umwelt',
    topic: 'climate_environment',
  },
  {
    id: 'q20',
    question:
      'Wie sollen Unternehmen dazu motiviert werden, ihren CO2-Ausstoß zu senken?',
    title: 'Klimaschutz und Umwelt',
    topic: 'climate_environment',
  },

  // Gesundheit und Pflege
  {
    id: 'q21',
    question: 'Wie kann das Gesundheitssystem effizienter gestaltet werden?',
    title: 'Gesundheit und Pflege',
    topic: 'health_care',
  },
  {
    id: 'q22',
    question: 'Welche Lösungen gibt es für den Pflegekräftemangel?',
    title: 'Gesundheit und Pflege',
    topic: 'health_care',
  },
  {
    id: 'q23',
    question:
      'Wie soll der Zugang zur Gesundheitsversorgung verbessert werden?',
    title: 'Gesundheit und Pflege',
    topic: 'health_care',
  },
  {
    id: 'q24',
    question:
      'Welche Maßnahmen gibt es zur Verbesserung der Krankenhausversorgung?',
    title: 'Gesundheit und Pflege',
    topic: 'health_care',
  },
  {
    id: 'q25',
    question: 'Wie kann die Prävention von Krankheiten gestärkt werden?',
    title: 'Gesundheit und Pflege',
    topic: 'health_care',
  },

  // Digitalisierung und Technologie
  {
    id: 'q26',
    question: 'Wie soll der Breitbandausbau beschleunigt werden?',
    title: 'Digitalisierung und Technologie',
    topic: 'digitalization_tech',
  },
  {
    id: 'q27',
    question:
      'Welche Maßnahmen sind zur Förderung Künstlicher Intelligenz geplant?',
    title: 'Digitalisierung und Technologie',
    topic: 'digitalization_tech',
  },
  {
    id: 'q28',
    question: 'Wie kann die digitale Verwaltung verbessert werden?',
    title: 'Digitalisierung und Technologie',
    topic: 'digitalization_tech',
  },
  {
    id: 'q29',
    question: 'Welche Vorschläge gibt es zur Verbesserung des Datenschutzes?',
    title: 'Digitalisierung und Technologie',
    topic: 'digitalization_tech',
  },
  {
    id: 'q30',
    question:
      'Wie kann die Tech-Branche in Deutschland besser gefördert werden?',
    title: 'Digitalisierung und Technologie',
    topic: 'digitalization_tech',
  },

  // Migration und Integration
  {
    id: 'q31',
    question: 'Wie wollen die Parteien die Asylpolitik reformieren?',
    title: 'Migration und Integration',
    topic: 'migration_integration',
  },
  {
    id: 'q32',
    question:
      'Welche Vorschläge gibt es zur besseren Integration von Migranten?',
    title: 'Migration und Integration',
    topic: 'migration_integration',
  },
  {
    id: 'q33',
    question: 'Wie kann die Steuerung der Einwanderung verbessert werden?',
    title: 'Migration und Integration',
    topic: 'migration_integration',
  },
  {
    id: 'q34',
    question: 'Welche Maßnahmen gibt es zur Bekämpfung von Fluchtursachen?',
    title: 'Migration und Integration',
    topic: 'migration_integration',
  },
  {
    id: 'q35',
    question: 'Wie sollen Anreize für legale Migration geschaffen werden?',
    title: 'Migration und Integration',
    topic: 'migration_integration',
  },

  // Innere Sicherheit und Justiz
  {
    id: 'q36',
    question: 'Welche Pläne gibt es zur Reform der Polizei?',
    title: 'Innere Sicherheit und Justiz',
    topic: 'security_justice',
  },
  {
    id: 'q37',
    question:
      'Wie kann die Kriminalitätsbekämpfung effektiver gestaltet werden?',
    title: 'Innere Sicherheit und Justiz',
    topic: 'security_justice',
  },
  {
    id: 'q38',
    question: 'Welche Maßnahmen gibt es gegen politischen Extremismus?',
    title: 'Innere Sicherheit und Justiz',
    topic: 'security_justice',
  },
  {
    id: 'q39',
    question: 'Wie sollen Bürgerrechte und Datenschutz gewährleistet werden?',
    title: 'Innere Sicherheit und Justiz',
    topic: 'security_justice',
  },
  {
    id: 'q40',
    question: 'Welche Vorschläge gibt es zur Modernisierung des Justizsystems?',
    title: 'Innere Sicherheit und Justiz',
    topic: 'security_justice',
  },

  // Außenpolitik und Europa
  {
    id: 'q41',
    question: 'Wie wollen die Parteien die Zusammenarbeit in der EU stärken?',
    title: 'Außenpolitik und Europa',
    topic: 'foreign_policy_europe',
  },
  {
    id: 'q42',
    question:
      'Welche Positionen gibt es zur Zukunft der NATO und der Bundeswehr?',
    title: 'Außenpolitik und Europa',
    topic: 'foreign_policy_europe',
  },
  {
    id: 'q43',
    question:
      'Wie sollen die Beziehungen zu China und den USA gestaltet werden?',
    title: 'Außenpolitik und Europa',
    topic: 'foreign_policy_europe',
  },
  {
    id: 'q44',
    question:
      'Welche Maßnahmen gibt es für eine stärkere gemeinsame EU-Verteidigung?',
    title: 'Außenpolitik und Europa',
    topic: 'foreign_policy_europe',
  },
  {
    id: 'q45',
    question:
      'Wie kann die wirtschaftliche Zusammenarbeit mit anderen Ländern verbessert werden?',
    title: 'Außenpolitik und Europa',
    topic: 'foreign_policy_europe',
  },

  // Verkehr und Infrastruktur
  {
    id: 'q46',
    question:
      'Welche Maßnahmen gibt es zur Verbesserung des öffentlichen Nahverkehrs?',
    title: 'Verkehr und Infrastruktur',
    topic: 'transport_infrastructure',
  },
  {
    id: 'q47',
    question: 'Wie soll der Ausbau des Bahnnetzes beschleunigt werden?',
    title: 'Verkehr und Infrastruktur',
    topic: 'transport_infrastructure',
  },
  {
    id: 'q48',
    question: 'Welche Maßnahmen gibt es zur Förderung der Elektromobilität?',
    title: 'Verkehr und Infrastruktur',
    topic: 'transport_infrastructure',
  },
  {
    id: 'q49',
    question: 'Wie kann der Verkehr klimafreundlicher gestaltet werden?',
    title: 'Verkehr und Infrastruktur',
    topic: 'transport_infrastructure',
  },
  {
    id: 'q50',
    question: 'Welche Konzepte gibt es für nachhaltige Stadtentwicklung?',
    title: 'Verkehr und Infrastruktur',
    topic: 'transport_infrastructure',
  },

  // Wohnungsbau und Mieten
  {
    id: 'q51',
    question: 'Welche Maßnahmen gibt es gegen steigende Mieten?',
    title: 'Wohnungsbau und Mieten',
    topic: 'housing_rent',
  },
  {
    id: 'q52',
    question: 'Wie wollen die Parteien den sozialen Wohnungsbau fördern?',
    title: 'Wohnungsbau und Mieten',
    topic: 'housing_rent',
  },
  {
    id: 'q53',
    question: 'Welche Konzepte gibt es zur Regulierung des Immobilienmarkts?',
    title: 'Wohnungsbau und Mieten',
    topic: 'housing_rent',
  },
  {
    id: 'q54',
    question:
      'Wie kann Wohnraum für Geringverdiener erschwinglicher gemacht werden?',
    title: 'Wohnungsbau und Mieten',
    topic: 'housing_rent',
  },
  {
    id: 'q55',
    question: 'Welche Anreize gibt es für nachhaltiges Bauen?',
    title: 'Wohnungsbau und Mieten',
    topic: 'housing_rent',
  },
];
