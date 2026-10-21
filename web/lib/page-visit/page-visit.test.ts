import { beforeEach, describe, expect, it } from 'bun:test';
import {
  PAGE_VISIT_MAX_VISIBLE_MS,
  checkpointVisibleMs,
  contextIdFromPath,
  currentVisibleMs,
  ensurePageVisitRuntime,
  getCurrentVisitId,
  loadOrCreatePageVisitSnapshot,
  markPageVisitCreated,
  resetPageVisitRuntimeForTests,
  setPageVisitStorageForTests,
  startVisibleSegment,
  stopVisibleSegment,
} from './page-visit';

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const data = { ...initial };
  return {
    get length() {
      return Object.keys(data).length;
    },
    clear() {
      for (const key of Object.keys(data)) {
        delete data[key];
      }
    },
    getItem(key: string) {
      return data[key] ?? null;
    },
    key() {
      return null;
    },
    removeItem(key: string) {
      delete data[key];
    },
    setItem(key: string, value: string) {
      data[key] = value;
    },
  };
}

describe('contextIdFromPath', () => {
  it('reads the first path segment as a context id', () => {
    expect(contextIdFromPath('/landtagswahl-sachsen-anhalt-2026/session')).toBe(
      'landtagswahl-sachsen-anhalt-2026',
    );
  });

  it('ignores reserved first segments', () => {
    expect(contextIdFromPath('/donate')).toBeUndefined();
    expect(contextIdFromPath('/agent/abc')).toBeUndefined();
    expect(contextIdFromPath('/')).toBeUndefined();
  });
});

describe('page visit accumulator', () => {
  beforeEach(() => {
    resetPageVisitRuntimeForTests();
    setPageVisitStorageForTests(memoryStorage());
  });

  it('creates a visit and accumulates only visible time', () => {
    ensurePageVisitRuntime('/', 1_000);
    startVisibleSegment(1_000);
    expect(stopVisibleSegment(4_000)).toBe(3_000);

    startVisibleSegment(10_000);
    expect(currentVisibleMs(12_000)).toBe(5_000);
    expect(stopVisibleSegment(13_000)).toBe(6_000);
  });

  it('does not double-start a visible segment', () => {
    ensurePageVisitRuntime('/', 0);
    startVisibleSegment(0);
    startVisibleSegment(500);
    expect(stopVisibleSegment(1_000)).toBe(1_000);
  });

  it('restores visible_ms across a reload in the same tab', () => {
    const storage = memoryStorage();
    setPageVisitStorageForTests(storage);
    ensurePageVisitRuntime('/bundestagswahl-2025', 0);
    startVisibleSegment(0);
    stopVisibleSegment(2_000);
    const visitId = getCurrentVisitId();

    resetPageVisitRuntimeForTests();
    const restored = loadOrCreatePageVisitSnapshot('/', 9_999);
    expect(restored.visitId).toBe(visitId);
    expect(restored.visibleMs).toBe(2_000);
    expect(restored.landingPath).toBe('/bundestagswahl-2025');
  });

  it('caps accumulated visible time', () => {
    ensurePageVisitRuntime('/', 0);
    startVisibleSegment(0);
    expect(stopVisibleSegment(PAGE_VISIT_MAX_VISIBLE_MS + 5_000)).toBe(
      PAGE_VISIT_MAX_VISIBLE_MS,
    );
  });

  it('remembers that the Firestore doc was created', () => {
    const snapshot = ensurePageVisitRuntime('/', 0);
    expect(snapshot.firestoreCreated).toBe(false);
    markPageVisitCreated();
    expect(loadOrCreatePageVisitSnapshot('/').firestoreCreated).toBe(true);
  });

  it('checkpoints an open segment so a crash restore is not behind Firestore', () => {
    ensurePageVisitRuntime('/', 0);
    startVisibleSegment(0);
    expect(checkpointVisibleMs(5_000)).toBe(5_000);
    const visitId = getCurrentVisitId();

    resetPageVisitRuntimeForTests();
    const restored = loadOrCreatePageVisitSnapshot('/', 9_999);
    expect(restored.visitId).toBe(visitId);
    expect(restored.visibleMs).toBe(5_000);
  });
});
