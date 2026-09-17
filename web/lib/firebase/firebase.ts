import type { WahlChatUser } from '@/components/anonymous-auth';
import {
  getCurrentVisitId,
  getOrLoadPageVisitSnapshot,
} from '@/lib/page-visit/page-visit';
import type { StudyCohort } from '@/lib/pledge-study/types';
import type { ProlificMetadata } from '@/lib/prolific-study/prolific-metadata';
import type {
  GroupedMessage,
  MessageFeedback,
  MessageItem,
  VotingBehavior,
} from '@/lib/stores/chat-store.types';
import { firestoreTimestampToDate, generateUuid } from '@/lib/utils';
import type { SwiperMessage } from '@/lib/wahl-swiper/wahl-swiper-store.types';
import type { WahlSwiperResultHistory } from '@/lib/wahl-swiper/wahl-swiper.types';
import { initializeApp } from 'firebase/app';
import { connectAuthEmulator, getAuth } from 'firebase/auth';
import {
  Timestamp,
  addDoc,
  arrayUnion,
  collection,
  connectFirestoreEmulator,
  doc,
  getDoc,
  getDocs,
  getFirestore,
  limit,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
  setDoc,
  updateDoc,
  where,
} from 'firebase/firestore';
import { firebaseConfig } from './firebase-config';
import {
  FIREBASE_EMULATOR_HOST,
  FIRESTORE_EMULATOR_PORT,
  authEmulatorUrl,
  firebaseEmulatorsEnabled,
} from './firebase-emulators';
import type {
  ChatSession,
  LlmSystemStatus,
  StudyParticipant,
  StudyParticipantEvent,
  StudyStatus,
} from './firebase.types';

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
const db = getFirestore(app);

// Route the browser SDKs at the local emulators when explicitly opted in, so a
// local session never authenticates against — or writes to — the real project.
// Must run before any auth/Firestore call; this module is a singleton so it runs
// once.
if (firebaseEmulatorsEnabled()) {
  connectAuthEmulator(auth, authEmulatorUrl(), { disableWarnings: true });
  connectFirestoreEmulator(db, FIREBASE_EMULATOR_HOST, FIRESTORE_EMULATOR_PORT);
}

/**
 * Best-effort Firebase ID-token auth header for backend requests.
 *
 * Returns `{ Authorization: 'Bearer <idToken>' }` when a user is signed in,
 * or `{}` when signed out or the token cannot be obtained — callers degrade
 * gracefully to an unauthenticated request instead of failing.
 */
export async function getAuthHeader(): Promise<Record<string, string>> {
  try {
    const user = auth.currentUser;
    if (!user) return {};
    const token = await user.getIdToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

export async function upsertPageVisit(payload: {
  visitId: string;
  userId: string;
  visibleMs: number;
  startedAtMs: number;
  landingPath: string;
  lastPath: string;
  contextId?: string;
  tenantId?: string;
  embedded?: boolean;
  chatSessionId?: string;
  includeCreateFields?: boolean;
}): Promise<void> {
  const data: Record<string, unknown> = {
    user_id: payload.userId,
    last_seen_at: Timestamp.now(),
    visible_ms: payload.visibleMs,
    last_path: payload.lastPath,
  };
  if (payload.includeCreateFields) {
    data.started_at = Timestamp.fromMillis(payload.startedAtMs);
    data.landing_path = payload.landingPath;
    if (payload.embedded) {
      data.embedded = true;
    }
  }
  if (payload.contextId) {
    data.context_id = payload.contextId;
  }
  if (payload.tenantId) {
    data.tenant_id = payload.tenantId;
  }
  if (payload.chatSessionId) {
    data.chat_session_ids = arrayUnion(payload.chatSessionId);
  }
  await setDoc(doc(db, 'page_visits', payload.visitId), data, { merge: true });
}

export async function attachChatSessionToPageVisit(
  visitId: string,
  sessionId: string,
  userId: string,
): Promise<void> {
  const snapshot = getOrLoadPageVisitSnapshot();
  const ref = doc(db, 'page_visits', visitId);
  const existing = await getDoc(ref);
  if (existing.exists()) {
    // Do not rewrite visible_ms — a heartbeat may already have flushed a
    // higher value, and the rules reject a decrease.
    await updateDoc(ref, {
      last_seen_at: Timestamp.now(),
      chat_session_ids: arrayUnion(sessionId),
    });
    return;
  }
  await setDoc(ref, {
    user_id: userId,
    last_seen_at: Timestamp.now(),
    chat_session_ids: arrayUnion(sessionId),
    started_at: Timestamp.fromMillis(snapshot.startedAtMs),
    visible_ms: snapshot.visibleMs,
    landing_path: snapshot.landingPath,
  });
}

export async function createChatSession(
  userId: string,
  partyIds: string[],
  sessionId: string,
  tenantId?: string,
  contextId?: string,
  prolificMetadata?: ProlificMetadata,
  studyCohort?: StudyCohort,
): Promise<void> {
  const visitId = getCurrentVisitId();
  await setDoc(doc(db, 'chat_sessions', sessionId), {
    user_id: userId,
    party_ids: partyIds,
    created_at: Timestamp.now(),
    updated_at: Timestamp.now(),
    ...(tenantId ? { tenant_id: tenantId } : {}),
    ...(contextId ? { context_id: contextId } : {}),
    ...(prolificMetadata
      ? { prolific_metadata: prolificMetadata, is_prolific_study: true }
      : {}),
    // PledgeTracker study: cohort stamp so chat data joins to the study
    // without an extra lookup (mirrors the prolific metadata pattern).
    ...(studyCohort
      ? { study_cohort: studyCohort, is_pledge_study: true }
      : {}),
    ...(visitId ? { visit_id: visitId } : {}),
  });
  if (visitId) {
    void attachChatSessionToPageVisit(visitId, sessionId, userId).catch(
      (error) => {
        console.error('Failed to attach chat session to page visit', error);
      },
    );
  }
}

export async function getUsersChatHistory(uid: string): Promise<ChatSession[]> {
  const history = await getDocs(
    query(
      collection(db, 'chat_sessions'),
      where('user_id', '==', uid),
      orderBy('updated_at', 'desc'),
      orderBy('created_at', 'desc'),
      limit(30),
    ),
  );

  return history.docs.map((doc) => ({
    id: doc.id,
    ...doc.data(),
  })) as ChatSession[];
}

export function listenToHistory(
  uid: string,
  callback: (history: ChatSession[]) => void,
) {
  const unsubscribe = onSnapshot(
    query(
      collection(db, 'chat_sessions'),
      where('user_id', '==', uid),
      orderBy('updated_at', 'desc'),
      orderBy('created_at', 'desc'),
      limit(15),
    ),
    (snapshot) => {
      callback(
        snapshot.docs.map((doc) => ({
          id: doc.id,
          ...doc.data(),
        })) as ChatSession[],
      );
    },
  );

  return unsubscribe;
}

export function listenToSystemStatus(
  callback: (status: LlmSystemStatus) => void,
) {
  const unsubscribe = onSnapshot(
    doc(db, 'system_status', 'llm_status'),
    (snapshot) => {
      callback({
        is_at_rate_limit: snapshot.data()?.is_at_rate_limit ?? false,
      });
    },
  );

  return unsubscribe;
}

/**
 * Kill switch for the PledgeTracker study: system_status/pledge_study
 * {enabled: true}. A missing doc, a missing field, or a listener error all
 * mean "study off" — the safe default. Flipping the flag is a console edit,
 * no deploy.
 */
export function listenToStudyStatus(callback: (status: StudyStatus) => void) {
  const unsubscribe = onSnapshot(
    doc(db, 'system_status', 'pledge_study'),
    (snapshot) => {
      callback({ enabled: snapshot.data()?.enabled === true });
    },
    () => callback({ enabled: false }),
  );

  return unsubscribe;
}

export async function getStudyParticipant(uid: string) {
  const snapshot = await getDoc(doc(db, 'study_participants', uid));
  return snapshot.exists() ? (snapshot.data() as StudyParticipant) : null;
}

export async function setStudyParticipant(
  uid: string,
  data: Partial<StudyParticipant>,
) {
  await setDoc(doc(db, 'study_participants', uid), data, { merge: true });
}

/** Append one interaction-log event (plus optional scalar merges). */
export async function appendStudyParticipantEvent(
  uid: string,
  event: StudyParticipantEvent,
  extra?: Partial<StudyParticipant>,
) {
  await setDoc(
    doc(db, 'study_participants', uid),
    { ...extra, events: arrayUnion(event) },
    { merge: true },
  );
}

export async function getChatSession(sessionId: string) {
  const session = await getDoc(doc(db, 'chat_sessions', sessionId));
  return {
    id: session.id,
    ...session.data(),
  } as ChatSession;
}

export async function getChatSessionMessages(sessionId: string) {
  const messagesRef = query(
    collection(db, 'chat_sessions', sessionId, 'messages'),
    orderBy('created_at', 'asc'),
  );

  const snapshot = await getDocs(messagesRef);
  return snapshot.docs.map((doc) => {
    const data = doc.data();
    return {
      ...data,
      id: doc.id,
      messages: data.messages.map((message: MessageItem) => ({
        ...message,
        created_at: firestoreTimestampToDate(message.created_at),
      })),
    } as GroupedMessage;
  });
}

export async function updateChatSession(
  sessionId: string,
  data: Partial<ChatSession>,
) {
  await updateDoc(doc(db, 'chat_sessions', sessionId), data);
}

export async function addMessageToGroupedMessageOfChatSession(
  sessionId: string,
  groupedMessageId: string,
  message: MessageItem,
) {
  await setDoc(
    doc(db, 'chat_sessions', sessionId, 'messages', groupedMessageId),
    {
      id: groupedMessageId,
      messages: arrayUnion(message),
      created_at: Timestamp.now(),
    },
    { merge: true },
  );
}

async function getGroupedMessage(sessionId: string, groupedMessageId: string) {
  const groupedMessage = await getDoc(
    doc(db, 'chat_sessions', sessionId, 'messages', groupedMessageId),
  );
  return {
    id: groupedMessage.id,
    ...groupedMessage.data(),
  } as GroupedMessage;
}

export async function addProConPerspectiveToMessage(
  sessionId: string,
  groupedMessageId: string,
  messageId: string,
  proConPerspective: MessageItem,
) {
  const groupedMessage = await getGroupedMessage(sessionId, groupedMessageId);

  const groupedMessageRef = doc(
    db,
    'chat_sessions',
    sessionId,
    'messages',
    groupedMessageId,
  );

  await updateDoc(groupedMessageRef, {
    messages: groupedMessage.messages.map((message: MessageItem) => {
      if (message.id === messageId) {
        return {
          ...message,
          pro_con_perspective: proConPerspective,
        };
      }

      return message;
    }),
  });
}

export async function addVotingBehaviorToMessage(
  sessionId: string,
  groupedMessageId: string,
  messageId: string,
  votingBehavior: VotingBehavior,
) {
  const groupedMessage = await getGroupedMessage(sessionId, groupedMessageId);

  const groupedMessageRef = doc(
    db,
    'chat_sessions',
    sessionId,
    'messages',
    groupedMessageId,
  );

  await updateDoc(groupedMessageRef, {
    messages: groupedMessage.messages.map((message: MessageItem) => {
      if (message.id === messageId) {
        return {
          ...message,
          voting_behavior: votingBehavior,
        };
      }

      return message;
    }),
  });
}

export async function addUserMessageToChatSession(
  sessionId: string,
  message: string,
) {
  const messageId = generateUuid();

  await setDoc(doc(db, 'chat_sessions', sessionId, 'messages', messageId), {
    id: messageId,
    messages: [
      {
        id: generateUuid(),
        content: message,
        sources: [],
        created_at: Timestamp.now(),
        role: 'user',
      },
    ],
    quick_replies: [],
    role: 'user',
    created_at: Timestamp.now(),
  } satisfies GroupedMessage);
}

export async function updateQuickRepliesOfMessage(
  sessionId: string,
  messageId: string,
  quickReplies: string[],
) {
  // Use setDoc with merge to handle race condition where quick_replies_and_title_ready
  // fires before the message document is created by party_response_complete
  await setDoc(
    doc(db, 'chat_sessions', sessionId, 'messages', messageId),
    { quick_replies: quickReplies },
    { merge: true },
  );
}

export async function updateTitleOfMessage(sessionId: string, title: string) {
  await updateDoc(doc(db, 'chat_sessions', sessionId), {
    title,
  });
}

export async function updateMessageInChatSession(
  sessionId: string,
  messageId: string,
  data: Partial<GroupedMessage>,
) {
  await updateDoc(
    doc(db, 'chat_sessions', sessionId, 'messages', messageId),
    data,
  );
}

export async function updateMessageFeedback(
  sessionId: string,
  groupedMessageId: string,
  messageId: string,
  feedback: MessageFeedback,
) {
  const groupedMessage = await getGroupedMessage(sessionId, groupedMessageId);

  const groupedMessageRef = doc(
    db,
    'chat_sessions',
    sessionId,
    'messages',
    groupedMessageId,
  );

  await updateDoc(groupedMessageRef, {
    messages: groupedMessage.messages.map((message: MessageItem) => {
      if (message.id === messageId) {
        return {
          ...message,
          feedback,
        };
      }

      return message;
    }),
  });
}

export async function getUser(uid: string) {
  const user = await getDoc(doc(db, 'users', uid));

  const data = user.data();

  return {
    id: user.id,
    ...data,
    survey_status: data?.survey_status
      ? {
          state: data.survey_status.state,
          timestamp: firestoreTimestampToDate(data.survey_status.timestamp),
        }
      : undefined,
  } as WahlChatUser;
}

export async function updateUser(uid: string, data: Partial<WahlChatUser>) {
  await setDoc(doc(db, 'users', uid), data, { merge: true });
}

export async function userAllowNewsletter(uid: string, allowed: boolean) {
  await setDoc(
    doc(db, 'users', uid),
    {
      newsletter_allowed: allowed,
    },
    { merge: true },
  );
}

export async function saveWahlSwiperHistory(
  userId: string,
  history: WahlSwiperResultHistory,
  chatMessages: Record<string, SwiperMessage[]>,
  prolificMetadata?: ProlificMetadata | null,
) {
  const collectionRef = collection(db, 'wahl_swiper_results');

  const docData: Record<string, unknown> = {
    user_id: userId,
    created_at: serverTimestamp(),
    history,
    chat_messages: chatMessages,
  };

  if (prolificMetadata) {
    docData.prolific_metadata = prolificMetadata;
    docData.is_prolific_study = true;
  }

  const docRef = await addDoc(collectionRef, docData);

  return docRef.id;
}

export async function setWahlSwiperResultToPublic(resultId: string) {
  await updateDoc(doc(db, 'wahl_swiper_results', resultId), {
    is_public: true,
  });
}
