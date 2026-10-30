export type Topic = keyof typeof TOPIC_TITLES;

/**
 * The site's topics, keyed by topic id, with each tag's colours. The titles
 * are not here: they live in the `topics` message namespace under the same
 * ids, so every language names a topic from one catalog.
 */
export const TOPIC_TITLES = {
  economy_finance: {
    normal: 'bg-blue-500/20 text-blue-500 border-blue-500/30',
    hover: 'hover:bg-blue-500/40 hover:text-blue-600 hover:border-blue-500/40',
    active:
      'bg-blue-500 text-white border-blue-700 hover:bg-blue-500/80 hover:text-white hover:border-blue-700',
  },
  social_labor: {
    normal: 'bg-green-500/20 text-green-500 border-green-500/30',
    hover:
      'hover:bg-green-500/40 hover:text-green-600 hover:border-green-500/40',
    active:
      'bg-green-500 text-white border-green-700 hover:bg-green-500/80 hover:text-white hover:border-green-700',
  },
  education_research: {
    normal: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
    hover:
      'hover:bg-yellow-500/40 hover:text-yellow-600 hover:border-yellow-500/40',
    active:
      'bg-yellow-500 text-black border-yellow-700 hover:bg-yellow-500/80 hover:text-black hover:border-yellow-700',
  },
  climate_environment: {
    normal: 'bg-green-700/20 text-green-700 border-green-700/30',
    hover:
      'hover:bg-green-700/40 hover:text-green-800 hover:border-green-700/40',
    active:
      'bg-green-700 text-white border-green-900 hover:bg-green-700/80 hover:text-white hover:border-green-900',
  },
  health_care: {
    normal: 'bg-red-500/20 text-red-500 border-red-500/30',
    hover: 'hover:bg-red-500/40 hover:text-red-600 hover:border-red-500/40',
    active:
      'bg-red-500 text-white border-red-700 hover:bg-red-500/80 hover:text-white hover:border-red-700',
  },
  digitalization_tech: {
    normal: 'bg-indigo-500/20 text-indigo-500 border-indigo-500/30',
    hover:
      'hover:bg-indigo-500/40 hover:text-indigo-600 hover:border-indigo-500/40',
    active:
      'bg-indigo-500 text-white border-indigo-700 hover:bg-indigo-500/80 hover:text-white hover:border-indigo-700',
  },
  migration_integration: {
    normal: 'bg-orange-500/20 text-orange-500 border-orange-500/30',
    hover:
      'hover:bg-orange-500/40 hover:text-orange-600 hover:border-orange-500/40',
    active:
      'bg-orange-500 text-black border-orange-700 hover:bg-orange-500/80 hover:text-black hover:border-orange-700',
  },
  security_justice: {
    normal:
      'bg-gray-700/20 text-gray-700 border-gray-700/30 dark:bg-gray-300/20 dark:text-gray-300 dark:border-gray-300/30',
    hover:
      'hover:bg-gray-700/40 hover:text-gray-800 hover:border-gray-700/40 dark:hover:bg-gray-300/30 dark:hover:text-gray-400 dark:hover:border-gray-300/40',
    active:
      'bg-gray-700 text-white border-gray-900 dark:bg-gray-300 dark:text-black dark:border-gray-500 hover:bg-gray-700/80 hover:text-white hover:border-gray-900 dark:hover:bg-gray-300/80 dark:hover:text-black dark:hover:border-gray-500',
  },
  foreign_policy_europe: {
    normal: 'bg-purple-500/20 text-purple-500 border-purple-500/30',
    hover:
      'hover:bg-purple-500/40 hover:text-purple-600 hover:border-purple-500/40',
    active:
      'bg-purple-500 text-white border-purple-700 hover:bg-purple-500/80 hover:text-white hover:border-purple-700',
  },
  transport_infrastructure: {
    normal: 'bg-blue-700/20 text-blue-700 border-blue-700/30',
    hover: 'hover:bg-blue-700/40 hover:text-blue-800 hover:border-blue-700/40',
    active:
      'bg-blue-700 text-white border-blue-900 hover:bg-blue-700/80 hover:text-white hover:border-blue-900',
  },
  housing_rent: {
    normal: 'bg-teal-500/20 text-teal-500 border-teal-500/30',
    hover: 'hover:bg-teal-500/40 hover:text-teal-600 hover:border-teal-500/40',
    active:
      'bg-teal-500 text-white border-teal-700 hover:bg-teal-500/80 hover:text-white hover:border-teal-700',
  },
};
