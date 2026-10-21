import { PAGE_VISIT_MAX_VISIBLE_MS } from '@/lib/page-visit/page-visit';

const VISIT_ID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export type PageVisitFlushBody = {
  visitId: string;
  visibleMs: number;
  lastPath?: string;
  landingPath?: string;
  startedAtMs?: number;
  contextId?: string;
  tenantId?: string;
  embedded?: boolean;
  idToken?: string;
};

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 && value.length <= 512
    ? value
    : undefined;
}

// Firebase ID tokens are JWTs (~900–2000 chars). Do not reuse the path cap.
function optionalIdToken(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 && value.length <= 4096
    ? value
    : undefined;
}

export function parsePageVisitFlushBody(
  body: unknown,
): { ok: true; data: PageVisitFlushBody } | { ok: false; error: string } {
  if (!body || typeof body !== 'object') {
    return { ok: false, error: 'Invalid body' };
  }
  const record = body as Record<string, unknown>;
  const visitId = record.visit_id;
  const visibleMs = record.visible_ms;
  if (typeof visitId !== 'string' || !VISIT_ID_RE.test(visitId)) {
    return { ok: false, error: 'Invalid visit_id' };
  }
  if (typeof visibleMs !== 'number' || !Number.isFinite(visibleMs)) {
    return { ok: false, error: 'Invalid visible_ms' };
  }
  const clamped = Math.min(
    Math.max(0, Math.round(visibleMs)),
    PAGE_VISIT_MAX_VISIBLE_MS,
  );
  const startedAtMs =
    typeof record.started_at_ms === 'number' &&
    Number.isFinite(record.started_at_ms)
      ? Math.round(record.started_at_ms)
      : undefined;
  return {
    ok: true,
    data: {
      visitId,
      visibleMs: clamped,
      lastPath: optionalString(record.last_path),
      landingPath: optionalString(record.landing_path),
      startedAtMs,
      contextId: optionalString(record.context_id),
      tenantId: optionalString(record.tenant_id),
      embedded: record.embedded === true,
      idToken: optionalIdToken(record.id_token),
    },
  };
}
