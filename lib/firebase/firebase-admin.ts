'use server';

import { CacheTags } from '@/lib/cache-tags';
import { GROUP_PARTY_ID } from '@/lib/constants';
import type {
  GroupedMessage,
  MessageItem,
} from '@/lib/stores/chat-store.types';
import { firestoreTimestampToDate } from '@/lib/utils';
import { credential } from 'firebase-admin';
import {
  type App as FirebaseApp,
  getApp,
  initializeApp,
} from 'firebase-admin/app';
import { Timestamp, getFirestore } from 'firebase-admin/firestore';
import { unstable_cache as cache } from 'next/cache';
import { getCurrentUser } from './firebase-server';
import type { ShareableChatSessionSnapshot, Tenant } from './firebase.types';

let app: FirebaseApp;

try {
  app = getApp();
} catch (error) {
  console.log('Initializing Firebase Admin App', error);

  const {
    NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    FIREBASE_CLIENT_EMAIL,
    FIREBASE_PRIVATE_KEY,
  } = process.env;

  if (
    !NEXT_PUBLIC_FIREBASE_PROJECT_ID ||
    !FIREBASE_CLIENT_EMAIL ||
    !FIREBASE_PRIVATE_KEY
  ) {
    throw new Error('Missing Firebase environment variables.');
  }

  app = initializeApp({
    credential: credential.cert({
      projectId: NEXT_PUBLIC_FIREBASE_PROJECT_ID,
      clientEmail: FIREBASE_CLIENT_EMAIL,
      privateKey: FIREBASE_PRIVATE_KEY.replace(/\\n/g, '\n'),
    }),
  });
}

const db = getFirestore(app);

export async function createShareableSession(sessionId: string) {
  const sessionRef = db.collection('chat_sessions').doc(sessionId);

  const session = await sessionRef.get();

  if (!session.exists) {
    throw new Error('Session not found');
  }

  const sessionData = session.data();

  if (!sessionData) {
    throw new Error('Session data not found');
  }

  const messagesRef = sessionRef.collection('messages');
  const messages = await messagesRef.get();

  const messagesData = messages.docs.map((doc) => doc.data());

  const shareableSessionSnapshotRef = await db
    .collection('shareable_chat_session_snapshots')
    .add({
      session_id: session.id,
      title: sessionData.title,
      shared_by: sessionData.user_id,
      party_ids: sessionData.party_ids,
      messages: messagesData,
      shared_at: Timestamp.now(),
    });

  await sessionRef.update({
    sharing_snapshot: {
      id: shareableSessionSnapshotRef.id,
      messages_length_at_sharing: messagesData.length,
    },
  });

  return {
    snapshot_id: shareableSessionSnapshotRef.id,
    messages_length_at_sharing: messagesData.length,
  };
}

export async function copySharedChatSession(
  snapshotId: string,
  userId: string,
) {
  const user = await getCurrentUser();

  if (!user) {
    throw new Error('User not found');
  }

  const snapshotRef = db
    .collection('shareable_chat_session_snapshots')
    .doc(snapshotId);
  const snapshot = await snapshotRef.get();
  if (!snapshot.exists) {
    throw new Error('Snapshot not found');
  }

  const data = snapshot.data();
  if (!data) {
    throw new Error('Snapshot data not found');
  }

  const batch = db.batch();
  const newSessionRef = db.collection('chat_sessions').doc();
  batch.set(newSessionRef, {
    created_at: Timestamp.now(),
    updated_at: Timestamp.now(),
    user_id: userId,
    party_ids: data.party_ids,
    title: data.title,
  });

  for (const message of data.messages) {
    batch.set(newSessionRef.collection('messages').doc(message.id), message);
  }

  await batch.commit();

  return {
    session_id: newSessionRef.id,
    session_type:
      data.party_ids.length > 1 ? GROUP_PARTY_ID : data.party_ids[0],
  };
}

export async function getSnapshotImpl(snapshotId: string) {
  const snapshotRef = db
    .collection('shareable_chat_session_snapshots')
    .doc(snapshotId);
  const snapshot = await snapshotRef.get();
  const data = snapshot.data();

  return {
    ...data,
    id: snapshot.id,
    shared_at: firestoreTimestampToDate(data?.shared_at),
    messages: data?.messages
      .map((message: GroupedMessage) => ({
        ...message,
        messages: message.messages.map((m: MessageItem) => ({
          ...m,
          created_at: firestoreTimestampToDate(m.created_at),
        })),
        created_at: firestoreTimestampToDate(message.created_at),
      }))
      .sort(
        (a: { created_at: Date }, b: { created_at: Date }) =>
          a.created_at.getTime() - b.created_at.getTime(),
      ),
  } as ShareableChatSessionSnapshot;
}

export const getSnapshot = cache(getSnapshotImpl, undefined, {
  revalidate: 60 * 60 * 24,
  tags: [CacheTags.SHAREABLE_CHAT_SESSION_SNAPSHOT],
});

export async function getTenantImpl(tenantId?: string | null) {
  if (!tenantId) {
    return;
  }

  const tenantRef = db.collection('tenants').doc(tenantId);
  const tenant = await tenantRef.get();

  if (!tenant.exists) {
    return;
  }

  return {
    id: tenant.id,
    ...tenant.data(),
  } as Tenant;
}

export const getTenant = cache(getTenantImpl, undefined, {
  revalidate: 60 * 60 * 24,
  tags: [CacheTags.TENANT],
});
