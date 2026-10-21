import { beforeEach, describe, expect, it, mock } from 'bun:test';
import {
  ensurePageVisitRuntime,
  resetPageVisitRuntimeForTests,
  setPageVisitStorageForTests,
} from './page-visit';

const upsertCalls: unknown[] = [];
let upsertDelayMs = 0;

mock.module('@/lib/firebase/firebase', () => ({
  upsertPageVisit: async (payload: unknown) => {
    upsertCalls.push(payload);
    if (upsertDelayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, upsertDelayMs));
    }
  },
}));

function memoryStorage(): Storage {
  const data: Record<string, string> = {};
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

describe('flushPageVisit queue', () => {
  beforeEach(() => {
    resetPageVisitRuntimeForTests();
    setPageVisitStorageForTests(memoryStorage());
    upsertCalls.length = 0;
    upsertDelayMs = 0;
  });

  it('coalesces a flush that arrives while another is in flight', async () => {
    const { flushPageVisit, resetPageVisitFlushForTests } = await import(
      './page-visit-flush'
    );
    resetPageVisitFlushForTests();
    ensurePageVisitRuntime('/', 0);

    upsertDelayMs = 20;
    const first = flushPageVisit({
      userId: 'user-1',
      pathname: '/',
    });
    const second = flushPageVisit({
      userId: 'user-1',
      pathname: '/landtagswahl-sachsen-anhalt-2026',
    });
    await Promise.all([first, second]);

    expect(upsertCalls.length).toBe(2);
    expect((upsertCalls[1] as { lastPath: string }).lastPath).toBe(
      '/landtagswahl-sachsen-anhalt-2026',
    );
  });
});
