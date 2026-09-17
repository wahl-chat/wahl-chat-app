import 'server-only';

import { getAuth } from 'firebase-admin/auth';
import { Timestamp } from 'firebase-admin/firestore';
import { getAdminApp, getAdminDb } from './firebase-admin-app';

export async function verifyFirebaseIdToken(idToken: string) {
  return getAuth(getAdminApp()).verifyIdToken(idToken);
}

export async function upsertPageVisitFromServer(payload: {
  visitId: string;
  userId: string;
  visibleMs: number;
  lastPath?: string;
  landingPath?: string;
  startedAtMs?: number;
  contextId?: string;
  tenantId?: string;
  embedded?: boolean;
}): Promise<void> {
  const ref = getAdminDb().collection('page_visits').doc(payload.visitId);
  const existing = await ref.get();
  if (existing.exists && existing.data()?.user_id !== payload.userId) {
    throw new Error('Page visit does not belong to this user');
  }

  const existingVisibleMs =
    typeof existing.data()?.visible_ms === 'number'
      ? existing.data()?.visible_ms
      : 0;
  const visibleMs = Math.max(existingVisibleMs ?? 0, payload.visibleMs);

  const data: Record<string, unknown> = {
    user_id: payload.userId,
    last_seen_at: Timestamp.now(),
    visible_ms: visibleMs,
  };
  if (!existing.exists) {
    if (payload.startedAtMs === undefined) {
      throw new Error('started_at_ms is required to create a page visit');
    }
    data.started_at = Timestamp.fromMillis(payload.startedAtMs);
    if (payload.landingPath) {
      data.landing_path = payload.landingPath;
    }
    if (payload.embedded) {
      data.embedded = true;
    }
  }
  if (payload.lastPath) {
    data.last_path = payload.lastPath;
  }
  if (payload.contextId) {
    data.context_id = payload.contextId;
  }
  if (payload.tenantId) {
    data.tenant_id = payload.tenantId;
  }

  await ref.set(data, { merge: true });
}
