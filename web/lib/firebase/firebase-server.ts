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
import { speakerPhotos } from '@/lib/daily/politicians';
import { editionIdOf, pageStart } from '@/lib/daily/window';
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
  type QueryConstraint,
  collection,
  connectFirestoreEmulator,
  doc,
  documentId,
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
  DigestParliamentId,
  ExampleQuestionShareableChatSession,
  FeedEdition,
  FeedItem,
  FeedPage,
  FirebaseWahlSwiperResult,
  GlossaryEntry,
  GlossarySource,
  LlmSystemStatus,
  ParliamentFeed,
  Politician,
  ProposedQuestion,
  SittingCalendar,
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

/**
 * The election-specific example questions for a context — the `group` slot.
 *
 * getProposedQuestionsForContext() with no partyIds resolves to
 * WAHL_CHAT_PARTY_ID, which holds meta questions about the product ("Wer steht
 * hinter wahl.chat?"). Questions about the election itself live under
 * GROUP_PARTY_ID; reaching them by passing a throwaway two-element partyIds
 * array would only work by accident of the normalisation, so this asks for the
 * slot directly.
 *
 * Order is deterministic, unlike getProposedQuestionsForContextImpl: this feeds
 * server-rendered HTML on the site's most-crawled page, so the same election
 * must always produce the same markup and the same set of outbound links.
 */
async function getGroupProposedQuestionsForContextImpl(contextId: string) {
  const serverDb = await getServerFirestore({ useHeaders: false });

  const queryRef = query(
    collection(
      serverDb,
      'contexts',
      contextId,
      'proposed_questions',
      GROUP_PARTY_ID,
      'questions',
    ),
    where('location', '==', 'chat'),
  );
  const snapshot = await getDocs(queryRef);

  const questions = snapshot.docs.map((doc) => {
    return {
      id: doc.id,
      partyId: GROUP_PARTY_ID,
      ...doc.data(),
    } as ProposedQuestion;
  });

  // rejectEmpty so a context seeded without a group doc is never pinned into
  // the data cache; seeding it later then heals on the next request.
  return rejectEmpty(questions.sort((a, b) => a.id.localeCompare(b.id)));
}

export async function getGroupProposedQuestionsForContext(contextId: string) {
  return uncachedFallback(
    () =>
      cachedRead(
        getGroupProposedQuestionsForContextImpl,
        ['getGroupProposedQuestionsForContext', 'v1', contextId],
        [CacheTags.PROPOSED_QUESTIONS, contextQuestionsTag(contextId)],
      )(contextId),
    [],
    `FAILED to fetch group proposed questions for context "${contextId}"`,
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

const DIGEST_PARLIAMENTS: readonly DigestParliamentId[] = [
  'bundestag',
  'landtag_st',
  'landtag_bw',
];
// A safety cap only: two weeks of one parliament are far fewer items.
const ITEMS_PER_PAGE = 500;
// Two sitting weeks of editions: more than are ever stored waiting for their
// items at once.
const ANCHOR_LOOKBACK = 10;

/**
 * The slice of one parliament's feed that ends on its newest edition with
 * items before `before` (or its newest overall): `FEED_WINDOW_DAYS` days back
 * from there, plus any newer days still waiting for their items. Anchoring on
 * an edition, not the calendar, skips recesses, so an older slice is never
 * empty while `hasOlder` is true.
 */
async function getFeedPageImpl(
  parliament: DigestParliamentId,
  before: string | null,
): Promise<FeedPage> {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const ofParliament = (name: string, ...constraints: QueryConstraint[]) =>
    getDocs(
      query(
        collection(serverDb, name),
        where('parliament', '==', parliament),
        ...(before ? [where('date', '<', before)] : []),
        ...constraints,
        orderBy('date', 'desc'),
      ),
    );

  // Anchored on a day stored before its items, the page would open empty.
  const newest = (
    await ofParliament('feed_editions', limit(ANCHOR_LOOKBACK))
  ).docs.map((d) => d.data() as FeedEdition);
  const anchor = (newest.find((e) => e.item_ids.length > 0) ?? newest[0])?.date;
  if (!anchor) {
    throw new UncacheableEmptyError();
  }
  const from = pageStart(anchor);
  const [editions, items, older] = await Promise.all([
    ofParliament('feed_editions', where('date', '>=', from)),
    ofParliament(
      'feed_items',
      where('date', '>=', from),
      limit(ITEMS_PER_PAGE),
    ),
    ofParliament('feed_editions', where('date', '<', from), limit(1)),
  ]);
  return {
    editions: rejectEmpty(editions.docs.map((d) => d.data() as FeedEdition)),
    items: items.docs.map((d) => d.data() as FeedItem),
    from,
    hasOlder: !older.empty,
  };
}

const EMPTY_PAGE: FeedPage = {
  editions: [],
  items: [],
  from: null,
  hasOlder: false,
};

/** The latest slice per parliament with its items, newest first. Both
 * languages come along, so switching language needs no round-trip. */
export async function getParliamentFeed(
  parliament: DigestParliamentId,
): Promise<FeedPage> {
  return uncachedFallback(
    () =>
      cachedRead(
        getFeedPageImpl,
        ['getParliamentFeed', 'v3', parliament],
        [CacheTags.FEED],
      )(parliament, null),
    EMPTY_PAGE,
    `FAILED to fetch the feed for "${parliament}"`,
  );
}

async function getFeedDayImpl(editionId: string): Promise<ParliamentFeed> {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const edition = await getDoc(doc(serverDb, 'feed_editions', editionId));
  if (!edition.exists()) {
    throw new UncacheableEmptyError();
  }
  const data = edition.data() as FeedEdition;
  const items = await getDocs(
    query(
      collection(serverDb, 'feed_items'),
      where('parliament', '==', data.parliament),
      where('date', '==', data.date),
    ),
  );
  return {
    editions: [data],
    items: items.docs.map((d) => d.data() as FeedItem),
  };
}

/** The sitting day of a shared item, so a link to an item older than the
 * first slice still opens it. Null when the key names no stored day. */
export async function getLinkedFeedDay(
  itemKey: string,
): Promise<ParliamentFeed | null> {
  const editionId = editionIdOf(itemKey);
  if (!editionId) {
    return null;
  }
  return uncachedFallback<ParliamentFeed | null>(
    () =>
      cachedRead(
        getFeedDayImpl,
        ['getLinkedFeedDay', 'v1', editionId],
        [CacheTags.FEED],
      )(editionId),
    null,
    `FAILED to fetch the feed day "${editionId}"`,
  );
}

/** The next older slice, for "Ältere Tage anzeigen". Called from the
 * browser, so both arguments are checked before they reach a query. */
export async function getOlderParliamentFeed(
  parliament: DigestParliamentId,
  before: string,
): Promise<FeedPage> {
  if (
    !DIGEST_PARLIAMENTS.includes(parliament) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(before)
  ) {
    return EMPTY_PAGE;
  }
  try {
    return await cachedRead(
      getFeedPageImpl,
      ['getOlderParliamentFeed', 'v2', parliament, before],
      [CacheTags.FEED],
    )(parliament, before);
  } catch (error) {
    // No older edition: the feed's real end. Any other failure has to reach
    // the client, which offers a retry; an empty page would read as the end.
    if (error instanceof UncacheableEmptyError) {
      return EMPTY_PAGE;
    }
    console.error(
      `[Firestore] FAILED to fetch older feed for "${parliament}" before ${before}:`,
      error,
    );
    throw error;
  }
}

// Firestore's `in` filter takes at most 30 values.
const IN_FILTER_MAX = 30;
// A debate rarely has more than a few dozen speakers.
const MAX_POLITICIANS = 120;
const MDB_ID = /^\d{1,12}$/;

async function getPoliticiansImpl(
  ids: string[],
): Promise<Record<string, Politician>> {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const found: Record<string, Politician> = {};
  for (let i = 0; i < ids.length; i += IN_FILTER_MAX) {
    const snapshot = await getDocs(
      query(
        collection(serverDb, 'politicians'),
        where(documentId(), 'in', ids.slice(i, i + IN_FILTER_MAX)),
      ),
    );
    for (const d of snapshot.docs) {
      found[d.id] = d.data() as Politician;
    }
  }
  return found;
}

async function getSpeakerPhotosImpl(
  ids: string[],
): Promise<Record<string, string>> {
  return speakerPhotos(await getPoliticiansImpl(ids));
}

/** The official portrait of each of these speakers, by MdB ID: all a
 * debate's chips need. The records stay on the server, so opening a debate
 * on a phone does not load every speaker's Angaben and votes. Called from
 * the browser, so the IDs are checked first. */
export async function getSpeakerPhotos(
  ids: string[],
): Promise<Record<string, string>> {
  const wanted = Array.isArray(ids)
    ? [...new Set(ids)]
        .filter((id) => typeof id === 'string' && MDB_ID.test(id))
        .sort()
    : [];
  if (wanted.length === 0 || wanted.length > MAX_POLITICIANS) {
    return {};
  }
  return uncachedFallback(
    () =>
      cachedRead(
        getSpeakerPhotosImpl,
        ['getSpeakerPhotos', 'v1', ...wanted],
        [CacheTags.FEED],
      )(wanted),
    {},
    'FAILED to fetch speaker photos',
  );
}

async function getPoliticianImpl(mdbId: string): Promise<Politician | null> {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const snapshot = await getDoc(doc(serverDb, 'politicians', mdbId));
  return snapshot.exists() ? (snapshot.data() as Politician) : null;
}

/** One speaker's record, read when their chip is tapped; null when the
 * Bundestag publishes none for them. */
export async function getPolitician(mdbId: string): Promise<Politician | null> {
  if (typeof mdbId !== 'string' || !MDB_ID.test(mdbId)) {
    return null;
  }
  return uncachedFallback(
    () =>
      cachedRead(
        getPoliticianImpl,
        ['getPolitician', 'v1', mdbId],
        [CacheTags.FEED],
      )(mdbId),
    null,
    'FAILED to fetch politician',
  );
}

async function getGlossaryImpl(): Promise<GlossaryEntry[]> {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const snapshot = await getDocs(
    query(collection(serverDb, 'glossary'), where('status', '==', 'verified')),
  );
  // An explanation is shown only with the source it was checked against.
  return snapshot.docs.flatMap((d) => {
    const { term_id, term, definition, forms, sources } = d.data();
    const linked = Array.isArray(sources)
      ? sources.filter(
          (s): s is GlossarySource =>
            typeof s?.url === 'string' && typeof s?.title === 'string',
        )
      : [];
    return typeof definition === 'string' && definition && linked.length > 0
      ? [
          {
            term_id,
            term,
            definition,
            forms: Array.isArray(forms) ? forms : [],
            sources: linked,
          },
        ]
      : [];
  });
}

/** Every explained term, for the whole feed at once: a few hundred short
 * entries at most, so the page needs no read per item. */
export async function getGlossary(): Promise<GlossaryEntry[]> {
  return uncachedFallback(
    () =>
      cachedRead(getGlossaryImpl, ['getGlossary', 'v2'], [CacheTags.FEED])(),
    [],
    'FAILED to fetch glossary',
  );
}

async function getSittingCalendarImpl(
  parliament: DigestParliamentId,
): Promise<SittingCalendar> {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const snapshot = await getDoc(doc(serverDb, 'feed_calendar', parliament));
  if (!snapshot.exists()) {
    throw new UncacheableEmptyError();
  }
  return snapshot.data() as SittingCalendar;
}

/** The parliament's next sitting weeks for the feed's "next sitting" line;
 * null when none are stored, which hides the line. */
export async function getSittingCalendar(
  parliament: DigestParliamentId,
): Promise<SittingCalendar | null> {
  return uncachedFallback<SittingCalendar | null>(
    () =>
      cachedRead(
        getSittingCalendarImpl,
        ['getSittingCalendar', 'v1', parliament],
        [CacheTags.FEED],
      )(parliament),
    null,
    `FAILED to fetch the sitting calendar for "${parliament}"`,
  );
}

async function getEditionDatesImpl(
  parliament: DigestParliamentId,
): Promise<string[]> {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const editions = await getDocs(
    query(
      collection(serverDb, 'feed_editions'),
      where('parliament', '==', parliament),
      orderBy('date', 'desc'),
    ),
  );
  // A day whose items were all retracted lists none: nothing to show.
  return rejectEmpty(
    editions.docs
      .map((d) => d.data() as FeedEdition)
      .filter((edition) => edition.item_ids.length > 0)
      .map((edition) => edition.date),
  );
}

/** The days the parliament's feed has content for, newest first: the sitting
 * calendar shows them as online. The feed only reaches back to its start, so
 * this stays a few dozen small documents a year. */
export async function getEditionDates(
  parliament: DigestParliamentId,
): Promise<string[]> {
  return uncachedFallback(
    () =>
      cachedRead(
        getEditionDatesImpl,
        ['getEditionDates', 'v1', parliament],
        [CacheTags.FEED],
      )(parliament),
    [],
    `FAILED to fetch the edition dates for "${parliament}"`,
  );
}

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
