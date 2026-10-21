import { upsertPageVisit } from '@/lib/firebase/firebase';
import {
  checkpointVisibleMs,
  contextIdFromPath,
  ensurePageVisitRuntime,
  getPageVisitSnapshot,
  markPageVisitCreated,
  stopVisibleSegment,
} from '@/lib/page-visit/page-visit';

export type PageVisitFlushContext = {
  userId: string;
  pathname: string;
  tenantId?: string;
  contextId?: string;
  embedded?: boolean;
  idToken?: string;
};

let flushInFlight = false;
let flushQueued = false;
let queuedContext: PageVisitFlushContext | null = null;

export function resetPageVisitFlushForTests(): void {
  flushInFlight = false;
  flushQueued = false;
  queuedContext = null;
}

function resolveContextId(ctx: PageVisitFlushContext): string | undefined {
  return ctx.contextId ?? contextIdFromPath(ctx.pathname);
}

function buildPayload(ctx: PageVisitFlushContext, visibleMs: number) {
  const snapshot =
    getPageVisitSnapshot() ?? ensurePageVisitRuntime(ctx.pathname);
  return {
    visitId: snapshot.visitId,
    userId: ctx.userId,
    visibleMs,
    startedAtMs: snapshot.startedAtMs,
    landingPath: snapshot.landingPath,
    lastPath: ctx.pathname || snapshot.landingPath,
    contextId: resolveContextId(ctx),
    tenantId: ctx.tenantId,
    embedded: ctx.embedded,
    includeCreateFields: !snapshot.firestoreCreated,
  };
}

export function sendUnloadFlush(
  ctx: PageVisitFlushContext,
  visibleMs: number,
): boolean {
  if (!ctx.idToken) {
    return false;
  }
  const snapshot =
    getPageVisitSnapshot() ?? ensurePageVisitRuntime(ctx.pathname);
  const body = {
    visit_id: snapshot.visitId,
    visible_ms: visibleMs,
    last_path: ctx.pathname || snapshot.landingPath,
    landing_path: snapshot.landingPath,
    started_at_ms: snapshot.startedAtMs,
    context_id: resolveContextId(ctx),
    tenant_id: ctx.tenantId,
    embedded: ctx.embedded === true,
    id_token: ctx.idToken,
  };
  const json = JSON.stringify(body);
  if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
    return navigator.sendBeacon(
      '/api/page-visit',
      new Blob([json], { type: 'application/json' }),
    );
  }
  if (typeof fetch === 'function') {
    void fetch('/api/page-visit', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${ctx.idToken}`,
        'Content-Type': 'application/json',
      },
      body: json,
      keepalive: true,
    });
    return true;
  }
  return false;
}

async function runFlush(ctx: PageVisitFlushContext): Promise<void> {
  const visibleMs = checkpointVisibleMs();
  try {
    await upsertPageVisit(buildPayload(ctx, visibleMs));
    markPageVisitCreated();
  } catch (error) {
    console.error('Failed to upsert page visit', error);
  }
}

export async function flushPageVisit(
  ctx: PageVisitFlushContext,
): Promise<void> {
  if (flushInFlight) {
    flushQueued = true;
    queuedContext = ctx;
    return;
  }
  flushInFlight = true;
  try {
    await runFlush(ctx);
    while (flushQueued && queuedContext) {
      const next = queuedContext;
      flushQueued = false;
      queuedContext = null;
      await runFlush(next);
    }
  } finally {
    flushInFlight = false;
  }
}

export function flushPageVisitOnHide(ctx: PageVisitFlushContext): void {
  stopVisibleSegment();
  const visibleMs = checkpointVisibleMs();
  sendUnloadFlush(ctx, visibleMs);
  void flushPageVisit(ctx);
}
