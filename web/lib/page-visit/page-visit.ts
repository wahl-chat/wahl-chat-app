import { generateUuid } from '@/lib/utils';

export const PAGE_VISIT_STORAGE_KEY = 'wahlchat_page_visit';
export const PAGE_VISIT_HEARTBEAT_MS = 20_000;
export const PAGE_VISIT_MAX_VISIBLE_MS = 7 * 24 * 60 * 60 * 1000;

const RESERVED_FIRST_SEGMENTS = new Set([
  'about-us',
  'agent',
  'api',
  'budget-spent',
  'datenschutz',
  'donate',
  'how-to',
  'impressum',
  'login',
  'session',
  'topics',
  '_next',
]);

export type PageVisitSnapshot = {
  visitId: string;
  startedAtMs: number;
  visibleMs: number;
  landingPath: string;
  firestoreCreated: boolean;
};

type RuntimeState = {
  snapshot: PageVisitSnapshot;
  segmentStartedAt: number | null;
};

type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

let runtime: RuntimeState | null = null;
let storageOverride: StorageLike | null | undefined;

export function setPageVisitStorageForTests(
  storage: StorageLike | null | undefined,
): void {
  storageOverride = storage;
}

export function resetPageVisitRuntimeForTests(): void {
  runtime = null;
}

function getStorage(): StorageLike | null {
  if (storageOverride !== undefined) {
    return storageOverride;
  }
  if (typeof sessionStorage === 'undefined') {
    return null;
  }
  return sessionStorage;
}

function clampVisibleMs(value: number): number {
  if (!Number.isFinite(value) || value < 0) {
    return 0;
  }
  return Math.min(Math.round(value), PAGE_VISIT_MAX_VISIBLE_MS);
}

function parseSnapshot(raw: string | null): PageVisitSnapshot | null {
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<PageVisitSnapshot>;
    if (
      typeof parsed.visitId !== 'string' ||
      parsed.visitId.length === 0 ||
      typeof parsed.startedAtMs !== 'number' ||
      typeof parsed.visibleMs !== 'number'
    ) {
      return null;
    }
    return {
      visitId: parsed.visitId,
      startedAtMs: parsed.startedAtMs,
      visibleMs: clampVisibleMs(parsed.visibleMs),
      landingPath:
        typeof parsed.landingPath === 'string' && parsed.landingPath.length > 0
          ? parsed.landingPath
          : '/',
      firestoreCreated: parsed.firestoreCreated === true,
    };
  } catch {
    return null;
  }
}

export function persistPageVisitSnapshot(snapshot: PageVisitSnapshot): void {
  const storage = getStorage();
  if (!storage) {
    return;
  }
  try {
    storage.setItem(PAGE_VISIT_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // sessionStorage can throw in private mode or when quota is exceeded.
  }
}

export function loadOrCreatePageVisitSnapshot(
  pathname: string,
  now = Date.now(),
): PageVisitSnapshot {
  const stored = parseSnapshot(
    getStorage()?.getItem(PAGE_VISIT_STORAGE_KEY) ?? null,
  );
  if (stored) {
    return stored;
  }
  return {
    visitId: generateUuid(),
    startedAtMs: now,
    visibleMs: 0,
    landingPath: pathname || '/',
    firestoreCreated: false,
  };
}

export function ensurePageVisitRuntime(
  pathname: string,
  now = Date.now(),
): PageVisitSnapshot {
  if (!runtime) {
    runtime = {
      snapshot: loadOrCreatePageVisitSnapshot(pathname, now),
      segmentStartedAt: null,
    };
    persistPageVisitSnapshot(runtime.snapshot);
  }
  return runtime.snapshot;
}

export function getCurrentVisitId(): string | undefined {
  if (runtime) {
    return runtime.snapshot.visitId;
  }
  return parseSnapshot(getStorage()?.getItem(PAGE_VISIT_STORAGE_KEY) ?? null)
    ?.visitId;
}

export function markPageVisitCreated(): void {
  if (!runtime) {
    return;
  }
  runtime.snapshot = { ...runtime.snapshot, firestoreCreated: true };
  persistPageVisitSnapshot(runtime.snapshot);
}

export function startVisibleSegment(now = Date.now()): void {
  if (!runtime || runtime.segmentStartedAt !== null) {
    return;
  }
  runtime.segmentStartedAt = now;
}

export function stopVisibleSegment(now = Date.now()): number {
  if (!runtime || runtime.segmentStartedAt === null) {
    return runtime?.snapshot.visibleMs ?? 0;
  }
  const elapsed = now - runtime.segmentStartedAt;
  runtime.snapshot = {
    ...runtime.snapshot,
    visibleMs: clampVisibleMs(runtime.snapshot.visibleMs + elapsed),
  };
  runtime.segmentStartedAt = null;
  persistPageVisitSnapshot(runtime.snapshot);
  return runtime.snapshot.visibleMs;
}

export function currentVisibleMs(now = Date.now()): number {
  if (!runtime) {
    return 0;
  }
  if (runtime.segmentStartedAt === null) {
    return runtime.snapshot.visibleMs;
  }
  return clampVisibleMs(
    runtime.snapshot.visibleMs + (now - runtime.segmentStartedAt),
  );
}

// Persist the value we are about to flush so a crash/restore cannot fall
// behind Firestore and fail the monotonic visible_ms rule.
export function checkpointVisibleMs(now = Date.now()): number {
  const visibleMs = currentVisibleMs(now);
  if (!runtime) {
    return visibleMs;
  }
  runtime.snapshot = { ...runtime.snapshot, visibleMs };
  if (runtime.segmentStartedAt !== null) {
    runtime.segmentStartedAt = now;
  }
  persistPageVisitSnapshot(runtime.snapshot);
  return visibleMs;
}

export function getPageVisitSnapshot(): PageVisitSnapshot | null {
  return runtime?.snapshot ?? null;
}

export function getOrLoadPageVisitSnapshot(pathname = '/'): PageVisitSnapshot {
  return getPageVisitSnapshot() ?? loadOrCreatePageVisitSnapshot(pathname);
}

export function contextIdFromPath(pathname: string): string | undefined {
  const first = pathname.split('/').find((segment) => segment.length > 0);
  if (!first || RESERVED_FIRST_SEGMENTS.has(first)) {
    return undefined;
  }
  return first;
}
