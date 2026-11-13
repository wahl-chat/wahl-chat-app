import { describe, expect, it } from 'bun:test';
import { claimOnce } from './claim-once';
import type { StorageLike } from './progress-store';

function fakeStorage(): StorageLike {
  const data: Record<string, string> = {};
  return {
    getItem: (key) => data[key] ?? null,
    setItem: (key, value) => {
      data[key] = value;
    },
  };
}

describe('claimOnce', () => {
  it('is true once per key, then false, as after a reload or in a second tab', () => {
    const storage = fakeStorage();
    expect(claimOnce(storage, 'stimmts:started:a')).toBe(true);
    expect(claimOnce(storage, 'stimmts:started:a')).toBe(false);
    expect(claimOnce(storage, 'stimmts:started:b')).toBe(true);
  });

  it('counts rather than loses an event when storage is missing or blocked', () => {
    expect(claimOnce(null, 'stimmts:started:a')).toBe(true);
    const blocked: StorageLike = {
      getItem: () => {
        throw new Error('blocked');
      },
      setItem: () => {
        throw new Error('blocked');
      },
    };
    expect(claimOnce(blocked, 'stimmts:started:a')).toBe(true);
  });
});
