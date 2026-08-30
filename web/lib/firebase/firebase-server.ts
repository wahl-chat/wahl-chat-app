'use server';

import type { FullUser } from '@/components/anonymous-auth';
import {
  CacheTags,
  contextPartiesTag,
  contextQuestionsTag,
  contextSourcesTag,
  contextTag,
} from '@/lib/cache-tags';
import { GROUP_PARTY_ID, WAHL_CHAT_PARTY_ID } from '@/lib/constants';
import type { PartyDetails } from '@/lib/party-details';
import type {
  GroupedMessage,
  MessageItem,
} from '@/lib/stores/chat-store.types';
import {
  firestoreTimestampToDate,
  makeFirebaseUserSerializable,
} from '@/lib/utils';
import type { WahlSwiperQuestion } from '@/lib/wahl-swiper/wahl-swiper.types';
import { initializeServerApp } from 'firebase/app';
import { connectAuthEmulator, getAuth } from 'firebase/auth';
import {
  collection,
  connectFirestoreEmulator,
  doc,
  getDoc,
  getDocs,
  getFirestore,
  limit,
  orderBy,
  query,
  where,
} from 'firebase/firestore';
import { unstable_cache } from 'next/cache';
import { headers } from 'next/headers';
import { firebaseConfig } from './firebase-config';
import {
  FIREBASE_EMULATOR_HOST,
  FIRESTORE_EMULATOR_PORT,
  authEmulatorUrl,
  firebaseEmulatorsEnabled,
} from './firebase-emulators';
import type {
  ChatSession,
  Context,
  ExampleQuestionShareableChatSession,
  FirebaseWahlSwiperResult,
  LlmSystemStatus,
  ProposedQuestion,
  SourceDocument,
} from './firebase.types';

class ContextNotFoundError extends Error {
  constructor(contextId: string) {
    super(`Context not found: ${contextId}`);
    this.name = 'ContextNotFoundError';
  }
}

// Thrown from inside unstable_cache so Next does not persist an empty list
// (or a miss). The wrapper converts it back to [] / undefined for callers.
class UncacheableEmptyError extends Error {
  constructor() {
    super('uncacheable empty');
    this.name = 'UncacheableEmptyError';
  }
}

// Safety net if on-demand revalidate is skipped. Election config is tag-busted
// on seed; this is only so a forgotten bust still heals within a day.
const SAFETY_REVALIDATE_SECONDS = 60 * 60 * 24;

function rejectEmpty<T>(items: T[]): T[] {
  if (items.length === 0) {
    throw new UncacheableEmptyError();
  }
  return items;
}

// Persistent-data-cache wrapper. In production this is unstable_cache. Against
// the local emulator it is a no-op passthrough: unstable_cache persists to
// .next/cache and survives dev-server restarts, so a successful-but-empty fetch
// (e.g. a read before the emulator is seeded) would otherwise stay pinned and
// mask freshly-seeded data. Local reads must be live.
function cache<A extends unknown[], R>(
  fn: (...args: A) => Promise<R>,
  keyParts?: string[],
  options?: { revalidate?: number | false; tags?: string[] },
): (...args: A) => Promise<R> {
  if (firebaseEmulatorsEnabled()) {
    return fn;
  }
  return unstable_cache(fn, keyParts, options);
}

function cachedRead<A extends unknown[], R>(
  fn: (...args: A) => Promise<R>,
  keyParts: string[],
  tags: string[],
): (...args: A) => Promise<R> {
  return cache(fn, keyParts, {
    revalidate: SAFETY_REVALIDATE_SECONDS,
    tags,
  });
}

async function uncachedFallback<T>(
  read: () => Promise<T>,
  fallback: T,
  logLabel: string,
): Promise<T> {
  try {
    return await read();
  } catch (error) {
    if (error instanceof UncacheableEmptyError) {
      return fallback;
    }
    console.error(`[Firestore] ${logLabel}:`, error);
    return fallback;
  }
}

async function getServerApp({
  useHeaders = true,
}: { useHeaders?: boolean } = {}) {
  let authIdToken: string | undefined;

  if (useHeaders) {
    const headersList = await headers();
    authIdToken = headersList.get('authorization')?.split(' ')[1];
  }

  return initializeServerApp(firebaseConfig, { authIdToken });
}

export async function getCurrentUser() {
  const serverApp = await getServerApp();
  const auth = getAuth(serverApp);
  if (firebaseEmulatorsEnabled()) {
    // A fresh server app per request; try/catch absorbs the "already connected"
    // throw if this instance was reused.
    try {
      connectAuthEmulator(auth, authEmulatorUrl(), { disableWarnings: true });
    } catch {
      /* already connected for this app instance */
    }
  }
  await auth.authStateReady();
  if (!auth.currentUser) {
    return null;
  }

  return auth.currentUser;
}

async function getServerFirestore({
  useHeaders = true,
}: { useHeaders?: boolean } = {}) {
  const serverApp = await getServerApp({ useHeaders });
  const db = getFirestore(serverApp);
  if (firebaseEmulatorsEnabled()) {
    try {
      connectFirestoreEmulator(
        db,
        FIREBASE_EMULATOR_HOST,
        FIRESTORE_EMULATOR_PORT,
      );
    } catch {
      /* already connected for this app instance */
    }
  }
  return db;
}

async function getPartiesImpl() {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const queryRef = query(
    collection(serverDb, 'parties'),
    orderBy('election_result_forecast_percent', 'desc'),
  );
  const snapshot = await getDocs(queryRef);

  return snapshot.docs.map((doc) => doc.data()) as PartyDetails[];
}

export const getParties = cache(getPartiesImpl, undefined, {
  revalidate: false,
  tags: [CacheTags.PARTIES],
});

async function getPartyImpl(partyId: string) {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const docRef = doc(serverDb, 'parties', partyId);
  const snapshot = await getDoc(docRef);

  if (!snapshot.exists) {
    return;
  }

  return snapshot.data() as PartyDetails;
}

export const getParty = cache(getPartyImpl, undefined, {
  revalidate: false,
  tags: [CacheTags.PARTIES],
});

// Context-related functions
async function getContextsImpl() {
  console.log('[Firestore] Fetching contexts (where is_active == true)');
  const serverDb = await getServerFirestore({ useHeaders: false });
  const queryRef = query(
    collection(serverDb, 'contexts'),
    where('is_active', '==', true),
  );
  const snapshot = await getDocs(queryRef);
  console.log(
    '[Firestore] Successfully fetched contexts:',
    snapshot.docs.length,
  );

  return rejectEmpty(
    snapshot.docs.map((doc) => {
      const data = doc.data();
      return {
        ...data,
        context_id: doc.id,
        date: firestoreTimestampToDate(data.date),
      } as unknown as Context;
    }),
  );
}

export async function getContexts() {
  return uncachedFallback(
    () =>
      cachedRead(
        getContextsImpl,
        ['getContexts', 'v3'],
        [CacheTags.CONTEXTS],
      )(),
    [],
    'FAILED to fetch contexts',
  );
}

async function getContextImpl(contextId: string) {
  console.log(`[Firestore] Fetching context: /contexts/${contextId}`);
  const serverDb = await getServerFirestore({ useHeaders: false });
  const docRef = doc(serverDb, 'contexts', contextId);
  const snapshot = await getDoc(docRef);

  if (!snapshot.exists()) {
    console.log(`[Firestore] Context not found: /contexts/${contextId}`);
    throw new ContextNotFoundError(contextId);
  }

  console.log(
    `[Firestore] Successfully fetched context: /contexts/${contextId}`,
  );
  const data = snapshot.data();
  return {
    ...data,
    context_id: snapshot.id,
    date: firestoreTimestampToDate(data?.date),
  } as unknown as Context;
}

export async function getContext(contextId: string) {
  try {
    return await cachedRead(
      getContextImpl,
      ['getContext', 'v4', contextId],
      [CacheTags.CONTEXTS, contextTag(contextId)],
    )(contextId);
  } catch (error) {
    if (error instanceof ContextNotFoundError) {
      return undefined;
    }
    console.error(
      `[Firestore] FAILED to fetch context "/contexts/${contextId}":`,
      error,
    );
    return undefined;
  }
}

async function getPartiesForContextImpl(contextId: string) {
  console.log(`[Firestore] Fetching parties: /contexts/${contextId}/parties`);
  const serverDb = await getServerFirestore({ useHeaders: false });
  const queryRef = query(
    collection(serverDb, 'contexts', contextId, 'parties'),
  );
  const snapshot = await getDocs(queryRef);
  console.log(
    `[Firestore] Successfully fetched parties for context: ${snapshot.docs.length} parties`,
  );

  return rejectEmpty(
    snapshot.docs.map((doc) => {
      const data = doc.data();
      return {
        ...data,
        party_id: doc.id,
      } as PartyDetails;
    }),
  );
}

export async function getPartiesForContext(contextId: string) {
  return uncachedFallback(
    () =>
      cachedRead(
        getPartiesForContextImpl,
        ['getPartiesForContext', 'v2', contextId],
        [CacheTags.CONTEXT_PARTIES, contextPartiesTag(contextId)],
      )(contextId),
    [],
    `FAILED to fetch parties "/contexts/${contextId}/parties"`,
  );
}

async function getPartyForContextImpl(contextId: string, partyId: string) {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const docRef = doc(serverDb, 'contexts', contextId, 'parties', partyId);
  const snapshot = await getDoc(docRef);

  if (!snapshot.exists()) {
    throw new UncacheableEmptyError();
  }

  const data = snapshot.data();
  return {
    ...data,
    party_id: snapshot.id,
  } as PartyDetails;
}

export async function getPartyForContext(contextId: string, partyId: string) {
  return uncachedFallback(
    () =>
      cachedRead(
        getPartyForContextImpl,
        ['getPartyForContext', 'v2', contextId, partyId],
        [CacheTags.CONTEXT_PARTIES, contextPartiesTag(contextId)],
      )(contextId, partyId),
    undefined,
    `Failed to fetch party "${partyId}" for context "${contextId}"`,
  );
}

export async function getPartiesForContextById(
  contextId: string,
  partyIds: string[],
) {
  const parties = await Promise.all(
    partyIds.map((partyId) => getPartyForContext(contextId, partyId)),
  );

  return parties.filter(Boolean) as PartyDetails[];
}

export async function getPartiesByIdImpl(partyIds: string[]) {
  const parties = await Promise.all(partyIds.map(getParty));

  return parties.filter(Boolean) as PartyDetails[];
}

export const getPartiesById = cache(getPartiesByIdImpl, undefined, {
  revalidate: false,
  tags: [CacheTags.PARTIES],
});

export async function getChatSession(sessionId: string) {
  const serverDb = await getServerFirestore();

  const sessionRef = doc(serverDb, 'chat_sessions', sessionId);

  const session = await getDoc(sessionRef);

  if (!session.exists) {
    return;
  }

  const data = session.data();

  if (!data) {
    return;
  }

  return {
    id: session.id,
    ...data,
    updated_at: firestoreTimestampToDate(data.updated_at),
    created_at: firestoreTimestampToDate(data.created_at),
  } as ChatSession;
}

export async function getUsersChatSessions(
  uid: string,
): Promise<ChatSession[]> {
  const serverDb = await getServerFirestore();
  const queryRef = query(
    collection(serverDb, 'chat_sessions'),
    where('user_id', '==', uid),
    orderBy('updated_at', 'desc'),
    orderBy('created_at', 'desc'),
    limit(15),
  );

  const snapshot = await getDocs(queryRef);

  return snapshot.docs.map((doc) => {
    const data = doc.data();
    return {
      id: doc.id,
      ...data,
      updated_at: firestoreTimestampToDate(data.updated_at),
      created_at: firestoreTimestampToDate(data.created_at),
    } as ChatSession;
  });
}

export async function getChatSessionMessages(sessionId: string) {
  const serverDb = await getServerFirestore();
  const messagesRef = query(
    collection(serverDb, 'chat_sessions', sessionId, 'messages'),
    orderBy('created_at', 'asc'),
  );
  const snapshot = await getDocs(messagesRef);
  return snapshot.docs.map((doc) => {
    const data = doc.data();
    return {
      ...data,
      id: doc.id,
      created_at: firestoreTimestampToDate(data.created_at),
      messages: data.messages.map((message: MessageItem) => ({
        ...message,
        created_at: firestoreTimestampToDate(message.created_at),
      })),
    } as GroupedMessage;
  });
}

async function getProposedQuestionsImpl(partyIds?: string[]) {
  const serverDb = await getServerFirestore({ useHeaders: false });

  const normalizedId = partyIds?.length
    ? partyIds.length > 1
      ? GROUP_PARTY_ID
      : partyIds[0]
    : WAHL_CHAT_PARTY_ID;

  const queryRef = query(
    collection(serverDb, 'proposed_questions', normalizedId, 'questions'),
    where('location', '==', 'chat'),
  );
  const snapshot = await getDocs(queryRef);

  const questions = snapshot.docs.map((doc) => {
    return {
      id: doc.id,
      partyId: normalizedId,
      ...doc.data(),
    } as ProposedQuestion;
  });

  return questions.sort(() => Math.random() - 0.5);
}

export const getProposedQuestions = cache(getProposedQuestionsImpl, undefined, {
  revalidate: 60 * 60 * 24,
  tags: [CacheTags.PROPOSED_QUESTIONS],
});

async function getProposedQuestionsForContextImpl(
  contextId: string,
  partyIds?: string[],
) {
  const serverDb = await getServerFirestore({ useHeaders: false });

  const normalizedId = partyIds?.length
    ? partyIds.length > 1
      ? GROUP_PARTY_ID
      : partyIds[0]
    : WAHL_CHAT_PARTY_ID;

  const path = `contexts/${contextId}/proposed_questions/${normalizedId}/questions`;
  console.log(`[Firestore] Fetching proposed questions: ${path}`);
  const queryRef = query(
    collection(
      serverDb,
      'contexts',
      contextId,
      'proposed_questions',
      normalizedId,
      'questions',
    ),
    where('location', '==', 'chat'),
  );
  const snapshot = await getDocs(queryRef);
  console.log(
    `[Firestore] Successfully fetched proposed questions: ${snapshot.docs.length} questions`,
  );

  const questions = snapshot.docs.map((doc) => {
    return {
      id: doc.id,
      partyId: normalizedId,
      ...doc.data(),
    } as ProposedQuestion;
  });

  return questions.sort(() => Math.random() - 0.5);
}

export async function getProposedQuestionsForContext(
  contextId: string,
  partyIds?: string[],
) {
  return uncachedFallback(
    () =>
      cachedRead(
        getProposedQuestionsForContextImpl,
        [
          'getProposedQuestionsForContext',
          'v2',
          contextId,
          JSON.stringify(partyIds ?? null),
        ],
        [CacheTags.PROPOSED_QUESTIONS, contextQuestionsTag(contextId)],
      )(contextId, partyIds),
    [],
    `FAILED to fetch proposed questions for context "${contextId}"`,
  );
}

async function getHomeInputProposedQuestionsImpl() {
  // Home questions are global, not context-specific
  // Read from /proposed_questions/wahl-chat/questions
  const path = `/proposed_questions/${WAHL_CHAT_PARTY_ID}/questions`;
  try {
    console.log(
      `[Firestore] Fetching home proposed questions: ${path} (where location == 'home')`,
    );
    const serverDb = await getServerFirestore({ useHeaders: false });
    const questionsRef = query(
      collection(
        serverDb,
        'proposed_questions',
        WAHL_CHAT_PARTY_ID,
        'questions',
      ),
      where('location', '==', 'home'),
    );
    const questionsSnapshot = await getDocs(questionsRef);
    console.log(
      `[Firestore] Successfully fetched home proposed questions: ${questionsSnapshot.docs.length} questions`,
    );

    return questionsSnapshot.docs.map((doc) => {
      return {
        id: doc.id,
        partyId: WAHL_CHAT_PARTY_ID,
        ...doc.data(),
      } as ProposedQuestion;
    });
  } catch (error) {
    console.error(
      `[Firestore] FAILED to fetch home proposed questions "${path}":`,
      error,
    );
    return [];
  }
}

export const getHomeInputProposedQuestions = cache(
  getHomeInputProposedQuestionsImpl,
  undefined,
  {
    revalidate: 60 * 60 * 24,
    tags: [CacheTags.HOME_PROPOSED_QUESTIONS],
  },
);

async function getSourceDocumentsImpl() {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const partiesRef = collection(serverDb, 'parties');
  const partiesSnapshot = await getDocs(partiesRef);

  const sourcesPromises = [
    ...partiesSnapshot.docs.map((doc) => doc.id),
    WAHL_CHAT_PARTY_ID,
  ].map(async (partyId) => {
    const sourcesRef = query(
      collection(serverDb, 'sources', partyId, 'source_documents'),
    );
    const sourcesSnapshot = await getDocs(sourcesRef);
    return sourcesSnapshot.docs.map((doc) => {
      const data = doc.data();
      return {
        ...data,
        id: doc.id,
        publish_date: firestoreTimestampToDate(data.publish_date),
        party_id: partyId,
      } as SourceDocument;
    });
  });

  const sources = await Promise.all(sourcesPromises);

  return sources.flat();
}

export const getSourceDocuments = cache(getSourceDocumentsImpl, undefined, {
  revalidate: 60 * 60 * 24,
  tags: [CacheTags.SOURCE_DOCUMENTS],
});

async function getSourceDocumentsForContextImpl(contextId: string) {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const partiesRef = collection(serverDb, 'contexts', contextId, 'parties');
  const partiesSnapshot = await getDocs(partiesRef);

  const sourcesPromises = [
    ...partiesSnapshot.docs.map((doc) => doc.id),
    WAHL_CHAT_PARTY_ID,
  ].map(async (partyId) => {
    const sourcesRef = query(
      collection(
        serverDb,
        'sources',
        contextId,
        'parties',
        partyId,
        'source_documents',
      ),
    );
    const sourcesSnapshot = await getDocs(sourcesRef);
    return sourcesSnapshot.docs.map((doc) => {
      const data = doc.data();
      return {
        ...data,
        id: doc.id,
        publish_date: firestoreTimestampToDate(data.publish_date),
        party_id: partyId,
      } as SourceDocument;
    });
  });

  const sources = await Promise.all(sourcesPromises);

  return sources.flat();
}

async function getSourceDocumentsForContextCached(contextId: string) {
  return rejectEmpty(await getSourceDocumentsForContextImpl(contextId));
}

export async function getSourceDocumentsForContext(contextId: string) {
  return uncachedFallback(
    () =>
      cachedRead(
        getSourceDocumentsForContextCached,
        ['getSourceDocumentsForContext', 'v2', contextId],
        [CacheTags.SOURCE_DOCUMENTS, contextSourcesTag(contextId)],
      )(contextId),
    [],
    `FAILED to fetch source documents for context "${contextId}"`,
  );
}

async function getExampleQuestionsShareableChatSessionImpl() {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const queryRef = query(
    collection(serverDb, 'shareable_chat_session_snapshots'),
    where('type', '==', 'example-question'),
  );
  const snapshot = await getDocs(queryRef);

  return snapshot.docs.map((doc) => {
    const data = doc.data();

    return {
      id: doc.id,
      question: data.question,
      topic: data.topic,
    } as ExampleQuestionShareableChatSession;
  });
}

export const getExampleQuestionsShareableChatSession = cache(
  getExampleQuestionsShareableChatSessionImpl,
  undefined,
  {
    revalidate: 60 * 60 * 24,
    tags: [CacheTags.EXAMPLE_QUESTIONS_SHAREABLE_CHAT_SESSIONS],
  },
);

export async function getSystemStatus() {
  const path = '/system_status/llm_status';
  try {
    console.log(`[Firestore] Fetching system status: ${path}`);
    const serverDb = await getServerFirestore({ useHeaders: false });
    const docRef = doc(serverDb, 'system_status', 'llm_status');
    const snapshot = await getDoc(docRef);
    console.log(`[Firestore] Successfully fetched system status: ${path}`);

    return {
      is_at_rate_limit: snapshot.data()?.is_at_rate_limit ?? false,
    } as LlmSystemStatus;
  } catch (error) {
    console.error(
      `[Firestore] FAILED to fetch system status "${path}":`,
      error,
    );
    return {
      is_at_rate_limit: false,
    } as LlmSystemStatus;
  }
}

export async function getWahlSwiperHistory(resultId: string) {
  const serverDb = await getServerFirestore();

  const docRef = doc(serverDb, 'wahl_swiper_results', resultId);
  const snapshot = await getDoc(docRef);

  return snapshot.data() as FirebaseWahlSwiperResult;
}

export async function getWahlSwiperThesesImpl() {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const queryRef = query(collection(serverDb, 'wahl_swiper_theses'));
  const snapshot = await getDocs(queryRef);

  return snapshot.docs.map((doc) => doc.data()) as WahlSwiperQuestion[];
}

export const getWahlSwiperTheses = cache(getWahlSwiperThesesImpl, undefined, {
  revalidate: 60 * 60 * 24,
  tags: [CacheTags.WAHL_SWIPER_THESES],
});

async function getWahlSwiperThesesForContextImpl(contextId: string) {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const queryRef = query(
    collection(serverDb, 'wahl_swiper_theses', contextId, 'theses'),
  );
  const snapshot = await getDocs(queryRef);

  return snapshot.docs.map((doc) => doc.data()) as WahlSwiperQuestion[];
}

export const getWahlSwiperThesesForContext = cache(
  getWahlSwiperThesesForContextImpl,
  undefined,
  {
    revalidate: 60 * 60 * 24,
    tags: [CacheTags.WAHL_SWIPER_THESES],
  },
);

export async function getUser() {
  try {
    console.log('[Firestore] Fetching current user...');
    const serverDb = await getServerFirestore();
    const currentUser = await getCurrentUser();

    if (!currentUser) {
      console.log('[Firestore] No current user found');
      return null;
    }

    const path = `/users/${currentUser.uid}`;
    console.log(`[Firestore] Fetching user document: ${path}`);
    const user = await getDoc(doc(serverDb, 'users', currentUser?.uid));
    console.log(`[Firestore] Successfully fetched user document: ${path}`);

    const data = user.data();

    return {
      ...makeFirebaseUserSerializable(currentUser),
      id: user.id,
      ...data,
      clicked_away_login_reminder: data?.clicked_away_login_reminder
        ? firestoreTimestampToDate(data.clicked_away_login_reminder)
        : undefined,
      survey_status: data?.survey_status
        ? {
            state: data.survey_status.state,
            timestamp: firestoreTimestampToDate(data.survey_status.timestamp),
          }
        : undefined,
    } as FullUser;
  } catch (error) {
    console.error('[Firestore] FAILED to fetch user:', error);
    return null;
  }
}
