export enum CacheTags {
  TENANT = 'tenant',
  PARTIES = 'parties',
  CONTEXTS = 'contexts',
  CONTEXT_PARTIES = 'context_parties',
  PROPOSED_QUESTIONS = 'proposed_questions',
  HOME_PROPOSED_QUESTIONS = 'home_proposed_questions',
  SOURCE_DOCUMENTS = 'source_documents',
  SHAREABLE_CHAT_SESSION_SNAPSHOT = 'shareable_chat_session_snapshot',
  EXAMPLE_QUESTIONS_SHAREABLE_CHAT_SESSIONS = 'example_questions_shareable_chat_sessions',
  WAHL_SWIPER_THESES = 'wahl_swiper_theses',
}

/** Per-election tags so a seed can bust one context without dropping the others. */
export function contextPartiesTag(contextId: string) {
  return `context:${contextId}:parties`;
}

export function contextSourcesTag(contextId: string) {
  return `context:${contextId}:sources`;
}

export function contextQuestionsTag(contextId: string) {
  return `context:${contextId}:questions`;
}

export function contextTag(contextId: string) {
  return `context:${contextId}`;
}
