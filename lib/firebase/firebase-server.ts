'use server';

import type { FullUser } from '@/components/anonymous-auth';
import { CacheTags } from '@/lib/cache-tags';
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
import { getAuth } from 'firebase/auth';
import {
  collection,
  doc,
  getDoc,
  getDocs,
  getFirestore,
  limit,
  orderBy,
  query,
  where,
} from 'firebase/firestore';
import { unstable_cache as cache } from 'next/cache';
import { headers } from 'next/headers';
import { firebaseConfig } from './firebase-config';
import type {
  ChatSession,
  ExampleQuestionShareableChatSession,
  FirebaseWahlSwiperResult,
  LlmSystemStatus,
  ProposedQuestion,
  SourceDocument,
} from './firebase.types';

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
  return getFirestore(serverApp);
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

async function getHomeInputProposedQuestionsImpl() {
  const serverDb = await getServerFirestore({ useHeaders: false });
  const questionsRef = query(
    collection(serverDb, 'proposed_questions', WAHL_CHAT_PARTY_ID, 'questions'),
    where('location', '==', 'home'),
  );
  const questionsSnapshot = await getDocs(questionsRef);

  return questionsSnapshot.docs.map((doc) => {
    return {
      id: doc.id,
      partyId: WAHL_CHAT_PARTY_ID,
      ...doc.data(),
    } as ProposedQuestion;
  });
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
  const serverDb = await getServerFirestore({ useHeaders: false });
  const docRef = doc(serverDb, 'system_status', 'llm_status');
  const snapshot = await getDoc(docRef);

  return {
    is_at_rate_limit: snapshot.data()?.is_at_rate_limit ?? false,
  } as LlmSystemStatus;
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

export async function getUser() {
  try {
    const serverDb = await getServerFirestore();
    const currentUser = await getCurrentUser();

    if (!currentUser) {
      return null;
    }

    const user = await getDoc(doc(serverDb, 'users', currentUser?.uid));

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
  } catch {
    return null;
  }
}
